"""JSON verb protocol shared by the daemon's socket server and the CLI
(canon: `canon/architecture/session-engine.md` "The Unix-Socket JSON Verb
Protocol").

Wire format: one line-delimited JSON object per request/response over the
unix-domain socket. Request: `{"verb": "...", "args": {...}}`. Response:
always has `"ok"`; on success carries verb-specific fields, on failure
carries `"error"`.

**WO-P2-020 Wave-3 SUBSET + WO-P2-025 control-lock wire** -- ported from
`archive/pre-rebirth-2026-07-23/code/twclient/protocol.py`. Live one-shot
verbs: `ensure`, `status`, `screen`, `stop`. Lifetime `attach` is handled
in `daemon.py` (not here). `do`/`send`/`read`/`history`/`state`/`set_mode`/
`subscribe`/`crawl_start`/`autopilot_*`/`record_*`/`replay`/`mine`/`play*`/
`haggle`/`list_skills` remain later WOs -- `dispatch()` returns
`unknown_verb` for them. Ensure rides `_driving_dispatch` (acquire_driver /
release_driver) for refuse-not-queue.

`build_response()` here is a bounded subset of archive protocol.py:407-470
-- see its own docstring for the exact fields cut and why.
"""

import json
import os
import time
from contextlib import contextmanager

from .classify import classify_screen
from .control_lock import (
    MODE_HUMAN,
    MODE_SPECTATE,
    ControlModeConflict,
)


def build_response(session, rows=None, settled_reason=None, extra=None):
    """WO-P2-020 Wave-3 CUT vs archive protocol.py:407-470: `color`
    (`session.render_with_color()` -- present on session.py but paired
    here with no color-consuming surface yet), `state`
    (`state_parser.parse_state` -- not ported, per this WO's Wave-2
    memory note), `cursor` (`session.cursor_pos()` -- the attach surface
    that reads it hasn't landed), the `world_identity`/`world_model`
    write hooks, `observe_credits`/`observe_turns`/`observe_fighters`
    (Session methods cut in Wave-2), and the `frame_recorder` post-mortem
    hook are all left off this response until their own work orders land.
    `sent_input` is kept -- it's a plain `Session` attribute (session.py,
    Wave-2), zero extra dependency."""
    if rows is None:
        rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    resp = {
        "ok": True,
        "screen": rows,
        "prompt": prompt,
        "classification": classify_screen(text, prompt),
        "sent_input": getattr(session, "last_sent", None),
    }
    if settled_reason is not None:
        resp["settled_reason"] = settled_reason
    if extra:
        resp.update(extra)
    return resp


def _control_lock_error(server):
    """Fast, non-atomic MODE hint for App driving verbs.

    None when App may claim the driver slot (no lock / mode app with no
    auto_loop hold). Otherwise a typed refuse naming who holds the
    keyboard. Atomic authority is still `acquire_driver()` inside
    `_driving_dispatch` — this is only the common-case early exit.
    """
    lock = getattr(server, "control_lock", None)
    if lock is None:
        return None
    if getattr(lock, "is_auto_loop_held", lambda: False)():
        return {"ok": False, "error": "controller_locked_by_auto_loop"}
    if lock.app_may_send():
        return None
    mode = lock.mode
    if mode == MODE_HUMAN:
        return {"ok": False, "error": "controller_locked_by_human"}
    if mode == MODE_SPECTATE:
        return {"ok": False, "error": "spectate_read_only"}
    return {"ok": False, "error": f"controller_locked:{mode}"}


@contextmanager
def _driving_dispatch(server):
    """Shared ensure/(future do/send) guard: mode hint + acquire_driver.

    Second concurrent App driver → typed refuse (`controller_busy` /
    `controller_locked_by_human` / `spectate_read_only` / …), never
    queued. Bare harness with no `control_lock` stays unrestricted
    (tests). Always release_driver on the way out.
    """
    lock_error = _control_lock_error(server)
    if lock_error is not None:
        yield lock_error
        return
    lock = getattr(server, "control_lock", None)
    if lock is None:
        yield None
        return
    try:
        lock.acquire_driver()
    except ControlModeConflict as e:
        yield {"ok": False, "error": str(e)}
        return
    try:
        yield None
    finally:
        lock.release_driver()


def dispatch(session, verb, args, server):
    """The daemon's one dispatch chokepoint. A malformed/unrecognized
    `verb` is answered with a structured error, never an exception --
    see `daemon.py`'s `CommandHandler.handle()` for the outer
    belt-and-braces `try/except` that also catches anything this misses."""
    if verb == "screen":
        rows = session.render_raw() if args.get("raw") else None
        return build_response(session, rows=rows)

    if verb == "status":
        # WO-P2-020 Wave-3 CUT vs archive: subscribers/play/credits*/turns*/
        # fighters*/intervention/world_id still deferred. Mode + autopilot
        # stub are live enough for cockpit status.
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        resp = {
            "ok": True,
            "connected": session.conn.connected,
            "idle_ms": int((time.monotonic() - session.last_rx) * 1000),
            "classification": classify_screen(text, prompt),
            "prompt": prompt,
            "host": session.host,
            "port": session.port,
            "name": session.name,
            # WO-P2-022: autopilot.py is not ported — ensure never arms.
            "autopilot": {"running": False},
        }
        lock = getattr(server, "control_lock", None)
        if lock is not None:
            mode = getattr(lock, "mode", None)
            if isinstance(mode, str):
                resp["mode"] = mode
        return resp

    if verb == "stop":
        server.request_stop()
        return {"ok": True, "stopping": True}

    if verb == "ensure":
        # WO-P2-025: full control-lock via `_driving_dispatch` (replaces
        # the earlier ensure-only `drive_lock`). Autopilot auto-arm after
        # ensure (`_maybe_auto_start_after_ensure`) still cut — no
        # autopilot.py.
        return _dispatch_ensure(session, args, server)

    return {"ok": False, "error": f"unknown_verb:{verb}"}


def _load_profile(name):
    """Bounded profile loader (WO-P2-020 Wave-3 CUT vs archive
    credentials.py:162-226's `load_profile`/`Profile`): no
    `crawl_sacrificial`/`autonomous` fields (`autopilot.py` hasn't
    landed). Reads `config/profiles.toml` directly via `tomllib` for the
    game_letter/handle/allow_register fields since the ported
    `credentials.py` (WO-P0-005/WO-P1-012) only exposes read-only
    summaries (`list_profile_summaries`), not a raw section lookup --
    host/port resolution itself is delegated to the ONE shared resolver,
    `credentials.resolve_profile_host_port` (OPEN-003-A). Returns
    `(LoginProfile, None)` on success, `(None, error_str)` on failure --
    never raises, so `_dispatch_ensure` can turn a bad profile into an
    ordinary `{"ok": False, ...}` response."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    from . import credentials
    from .login import LoginProfile

    path = credentials.PROFILES_PATH
    if not path.exists():
        return None, f"profile_not_found:{name}"
    with open(path, "rb") as f:
        data = tomllib.load(f)
    p = data.get(name)
    if not isinstance(p, dict):
        return None, f"profile_not_found:{name}"

    game_letter = p.get("game_letter")
    handle = p.get("handle")
    allow_register = bool(p.get("allow_register", False))
    missing = []
    if not game_letter:
        missing.append("game_letter")
    if not handle and not allow_register:
        missing.append("handle")
    if missing:
        return None, f"profile_incomplete:{name}:missing={missing}"

    try:
        host, port = credentials.resolve_profile_host_port(name)
    except credentials.ProfileConnectionError as e:
        return None, f"profile_connection_error:{name}:{e}"

    profile = LoginProfile(
        name=name,
        handle=handle,
        game_letter=str(game_letter),
        allow_register=allow_register,
        ship_name=p.get("ship_name"),
        planet_name=p.get("planet_name"),
        clear_avoids_on_login=bool(p.get("clear_avoids_on_login", False)),
    )
    return profile, None


def _save_password(profile_name, password):
    """NEW-registration credential persistence (login-automaton.md:
    "generates a fresh password and saves it immediately"). WO-P2-020
    Wave-3 CUT vs archive credentials.py:268-278's `save_password`: the
    ported `credentials.py` (WO-P0-005/WO-P1-012) only landed the READ
    side (`get_password`) -- this mirrors its EXACT on-disk shape
    (`{profile: {"password": ...}}`) at the same chmod-600
    `SECRETS_PATH` so a later `credentials.get_password(profile_name)`
    call reads it straight back. A follow-on WO should promote this into
    `credentials.py` itself rather than leaving the write side split
    across two modules."""
    from . import credentials

    path = credentials.SECRETS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[profile_name] = {"password": password}
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.chmod(tmp_path, 0o600)
    os.replace(str(tmp_path), str(path))
    os.chmod(path, 0o600)


def _dispatch_ensure(session, args, server):
    """B4: idempotent `ensure` -- classify the current screen; if already
    at `target`, no-op. Else run the login automaton via the profile's
    stored/generated credential.

    **WO-P2-025:** whole body runs under `_driving_dispatch` (control_lock
    `acquire_driver` / `release_driver`). Concurrent second ensure →
    typed `controller_busy` (or human/spectate/auto_loop refuse), never
    queued — folds the earlier ensure-only `drive_lock`. Bare harness
    without `server.control_lock` stays unrestricted for unit tests.
    Login sends use Session.send default `sender="app"` (no login edits).
    """
    with _driving_dispatch(server) as lock_error:
        if lock_error is not None:
            return lock_error

        from . import credentials
        from .login import LoginError, run_login

        target = args.get("target", "main_command")
        profile_name = args.get("profile")
        # WO-P2-022: `no_auto_arm` is accepted on the wire for symmetry with any
        # future default-arm proposal, but ensure NEVER auto-arms today
        # (`autopilot.py` not ported; `_maybe_auto_start_after_ensure` left out).
        # When auto-arm returns, it MUST gate on `bool(args.get("no_auto_arm"))`.
        _ = bool(args.get("no_auto_arm"))
        if not profile_name:
            return {"ok": False, "error": "missing_profile"}

        profile, err = _load_profile(profile_name)
        if err is not None:
            return {"ok": False, "error": err}

        # A dead telnet connection must be repaired before we can even
        # classify the current screen (a stale pyte buffer would
        # misclassify a frozen last-seen frame as "current").
        if not session.conn.connected:
            try:
                session.reconnect()
            except OSError as e:
                return {"ok": False, "error": f"reconnect_failed:{e}"}

        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        cls = classify_screen(text, prompt)

        if cls == target:
            session.mark_profile(profile.name)
            return build_response(session, extra={"already_there": True, "steps": 0})

        try:
            final_cls, steps = run_login(
                session,
                profile,
                get_password=credentials.get_password,
                save_password=_save_password,
                target=target,
            )
        except LoginError as e:
            resp = build_response(session, extra={"already_there": False})
            resp["ok"] = False
            resp["error"] = f"login_failed:{e}"
            return resp

        session.mark_profile(profile.name)
        return build_response(session, extra={"steps": steps, "already_there": False})
