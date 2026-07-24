"""JSON verb protocol shared by the daemon's socket server and the CLI
(canon: `canon/architecture/session-engine.md` "The Unix-Socket JSON Verb
Protocol").

Wire format: one line-delimited JSON object per request/response over the
unix-domain socket. Request: `{"verb": "...", "args": {...}}`. Response:
always has `"ok"`; on success carries verb-specific fields, on failure
carries `"error"`.

**WO-P2-020 Wave-3 SUBSET** -- ported from
`archive/pre-rebirth-2026-07-23/code/twclient/protocol.py` (2011 lines,
~30 verbs), this module carries only the four verbs the reborn
`ensure`-to-`main_command` core needs: `ensure`, `status`, `screen`,
`stop`. `do`/`send`/`read`/`history`/`state`/`set_mode`/`subscribe`/
`attach`/`crawl_start`/`autopilot_*`/`record_*`/`replay`/`mine`/`play*`/
`haggle`/`list_skills` are all later WOs -- `dispatch()` below returns
`unknown_verb` for every one of them rather than silently no-opping.
Every response field name below matches the archive's exact wire shape
(`"screen"`, `"prompt"`, `"classification"`, ...) so `cli.py`'s matching
client (ported from the same archive) composes against it unchanged.

`build_response()` here is a bounded subset of archive protocol.py:407-470
-- see its own docstring for the exact fields cut and why.
"""

import json
import os
import threading
import time

from .classify import classify_screen


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


def dispatch(session, verb, args, server):
    """The daemon's one dispatch chokepoint. A malformed/unrecognized
    `verb` is answered with a structured error, never an exception --
    see `daemon.py`'s `CommandHandler.handle()` for the outer
    belt-and-braces `try/except` that also catches anything this misses."""
    if verb == "screen":
        rows = session.render_raw() if args.get("raw") else None
        return build_response(session, rows=rows)

    if verb == "status":
        # WO-P2-020 Wave-3 CUT vs archive protocol.py:590-767: `mode`
        # (`control_lock.py` not ported), `subscribers`/`play`
        # (`watch.py`/`loop_player.py` not ported), full `autopilot_trace`
        # (`autopilot.py` not ported), `credits*`/`turns*`/`fighters*`
        # (Session's observe_* methods cut in Wave-2), `intervention`, and
        # `world_id` are all left off this response until their own work
        # orders land. WO-P2-022 adds a stub `autopilot: {running: false}`
        # so status --json can prove ensure never arms. This deliberately
        # does NOT require `state_parser` (per this WO's context block).
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        return {
            "ok": True,
            "connected": session.conn.connected,
            "idle_ms": int((time.monotonic() - session.last_rx) * 1000),
            "classification": classify_screen(text, prompt),
            "prompt": prompt,
            "host": session.host,
            "port": session.port,
            "name": session.name,
            # WO-P2-022: autopilot.py is not ported — ensure never arms. Expose
            # an honest "not driving" stub so `status --json` can prove Accept
            # ("App is not actively driving") until the real autopilot surface lands.
            "autopilot": {"running": False},
        }

    if verb == "stop":
        server.request_stop()
        return {"ok": True, "stopping": True}

    if verb == "ensure":
        # WO-P2-020 Wave-3 CUT vs archive protocol.py:791-802: the FULL
        # `_driving_dispatch`/control-lock module (modes, human
        # preemption/fencing, `controller_locked_by_human`/
        # `controller_locked_by_auto_loop`) is NOT ported -- that's still
        # `control_lock.py`'s own later work order. What IS ported (Mack
        # adversarial-review fix, HIGH): a minimal per-daemon exclusive
        # DRIVE LOCK, just enough to stop two concurrent `ensure` calls
        # from interleaving sends onto the SAME login automaton run (a
        # real ThreadingUnixServer trigger -- a caller retrying `ensure`
        # after a timeout lands a 2nd driver thread against the still-live
        # 1st). See `_dispatch_ensure`'s own docstring. The post-login
        # `_maybe_auto_start_after_ensure` autopilot auto-arm
        # (`autopilot.py` not ported) is still left out entirely.
        return _dispatch_ensure(session, args, server)

    return {"ok": False, "error": f"unknown_verb:{verb}"}


def _load_profile(name):
    """Bounded profile loader (WO-P2-020 Wave-3 CUT vs archive
    credentials.py:162-226's `load_profile`/`Profile`): no server-catalog
    multi-front-end resolution beyond the plain host/port `list_servers()`
    lookup the ported `credentials.py` (Wave-1) already exposes, and no
    `crawl_sacrificial`/`autonomous` fields (`autopilot.py` hasn't
    landed). Reads `config/profiles.toml` directly via `tomllib` since
    the ported `credentials.py` (WO-P0-005/WO-P1-012) only exposes
    read-only summaries (`list_profile_summaries`), not a raw section
    lookup. Returns `(LoginProfile, None)` on success, `(None, error_str)`
    on failure -- never raises, so `_dispatch_ensure` can turn a bad
    profile into an ordinary `{"ok": False, ...}` response."""
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

    host = p.get("host")
    port = p.get("port")
    server_key = p.get("server")
    if server_key and (host is None or port is None):
        catalog = {str(s["key"]): s for s in credentials.list_servers()}
        rec = catalog.get(server_key)
        if rec is None:
            return None, f"profile_server_unresolved:{name}:unknown_server={server_key}"
        host = host if host is not None else rec["host"]
        port = port if port is not None else rec["port"]
    if host is None or port is None:
        return None, f"profile_incomplete:{name}:missing=['host_or_port']"

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

    **Mack adversarial-review fix (HIGH, reproduced):** the whole body
    below (fast-check included) now runs under a per-daemon exclusive
    `server.drive_lock`. `ThreadingUnixServer` (daemon.py) is
    `daemon_threads=True` -- without this, two concurrent `ensure`
    connections (the real trigger: a caller's `ensure_session(timeout=..)`
    times out client-side and retries while the FIRST daemon-side
    `run_login` is still mid-flight) can both drive `run_login()` against
    the SAME `Session` at once. Both threads' sends interleave onto the
    ONE wire, desyncing it, yet -- because each thread's own local view of
    "did my last send get confirmed" can still spuriously read true --
    BOTH can return `ok=True`/`main_command`, a false-success double-drive
    that violates the single-connection invariant just as surely as two
    daemons would. `acquire(blocking=False)` makes a second concurrent
    `ensure` fail FAST with a typed, non-blocking refusal instead of
    queueing behind (and corrupting) the first -- refuse-not-queue, same
    posture the full `control_lock.py` module will later generalize.
    `getattr(...)`-lazy so a minimal test double `server` (one that never
    pre-populates `drive_lock`, the way this module's OWN dispatch tests
    might) still gets correct mutual exclusion rather than an
    AttributeError.

    The `controller_busy` error string (not a locally-invented one) is
    deliberate: `tw2002_aiclient/adapters.py::_classify_failure` already
    maps any `error` starting with `"controller_"` to
    `REASON_ALREADY_DRIVING`, carrying an explicit FLAG comment asking
    this WO to confirm the daemon actually emits that vocabulary (per
    `canon/architecture/session-engine.md`'s `ControlModeConflict`
    naming: `controller_locked_by_human` / `controller_locked_by_auto_loop`
    / `controller_busy`). This closes that flag now, ahead of
    `control_lock.py` itself landing."""
    lock = getattr(server, "drive_lock", None)
    if lock is None:
        lock = threading.Lock()
        server.drive_lock = lock
    if not lock.acquire(blocking=False):
        return {
            "ok": False,
            "error": "controller_busy",
            "detail": "another ensure/drive is already in progress on this daemon",
        }
    try:
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
    finally:
        lock.release()
