"""``tw`` — the backend/ops CLI. Talks to ``twd`` over its unix socket.

Most verbs are a single connect -> send JSON -> read JSON line -> disconnect
round trip. Lifetime socket holds are the exceptions: ``tw watch`` keeps a
``subscribe`` stream open (NDJSON settle-edge events) until ``--frames N`` or
Ctrl-C, and ``tw attach`` holds a session socket for interactive keystrokes
(see canon `architecture/session-engine.md`). Verb table grows one WO at a
time; ``ensure``/``status`` land under WO-P2-020 -- APPEND new verbs to
``build_parser()``, never rewrite an already-landed one.
"""

from __future__ import annotations

import errno
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import argparse

from . import credentials, env
from .tty_encode import print_tty


class ProfileResolutionError(Exception):
    """Raised when a profile name cannot be resolved to a connectable
    (host, port) -- missing section, missing host/port, or an unknown
    `server` catalog key."""


def _resolve_run_dir(run_dir_arg: str | None) -> Path:
    """Layer a per-invocation `--run-dir` CLI override on top of
    `env.resolve_run_dir()`'s `TW_RUN_DIR`-env-var default (e.g.
    `--run-dir run/ona` for an isolated daemon socket)."""
    if run_dir_arg is None:
        return env.resolve_run_dir()
    p = Path(run_dir_arg)
    return p if p.is_absolute() else (env.PROJECT_ROOT / p)


def _config_isolation_active() -> bool:
    """True when the operator isolated config away from project ``config/``.

    ``TW_CONFIG_DIR`` is the live signal (env-first). We also treat a resolved
    ``credentials.CONFIG_DIR`` that is not the project default as isolation —
    same axis, in case a test reloads credentials against a tmp dir.
    Isolating config does **not** isolate the daemon socket (``run/`` /
    ``TW_RUN_DIR`` / ``--run-dir``); that mismatch is the matrix footgun.
    """
    if os.environ.get("TW_CONFIG_DIR"):
        return True
    default = (env.PROJECT_ROOT / "config").resolve()
    try:
        return Path(credentials.CONFIG_DIR).resolve() != default
    except OSError:
        return True


def _guard_run_dir_footgun(args) -> int | None:
    """Fail closed when config is isolated but the run-dir axis is not named.

    WO-CLI-RUN-DIR-FOOTGUN-WARN: ``TW_CONFIG_DIR`` (or a non-default config
    dir) without ``--run-dir`` / ``TW_RUN_DIR`` would silently target the
    default daemon socket — including ``status`` / ``stop`` / ``ensure``.
    Refuse before any socket touch; print the path that *would* have been
    used so the operator can pass it deliberately.

    Returns an exit code when blocked; ``None`` when the call may proceed.
    """
    if getattr(args, "run_dir", None) is not None:
        return None
    if os.environ.get(env.RUN_DIR_VAR):
        return None
    if not _config_isolation_active():
        return None
    would_target = _resolve_run_dir(None)
    detail = (
        "TW_CONFIG_DIR (or a non-default config dir) is set, but --run-dir "
        "was not given and TW_RUN_DIR is unset. Isolating config does NOT "
        f"isolate the daemon socket. Would have targeted run-dir: {would_target}. "
        "Pass --run-dir PATH (or set TW_RUN_DIR) to name the intended daemon."
    )
    if getattr(args, "json", False):
        print(json.dumps({
            "ok": False,
            "error": "run_dir_required_under_config_isolation",
            "detail": detail,
            "run_dir": str(would_target),
        }))
    else:
        print(f"ERROR: {detail}", file=sys.stderr)
    return 2


def _resolve_profile_connection(profile_name: str) -> tuple[str, int]:
    """Resolve `profile_name`'s (host, port) via the ONE shared resolver,
    `credentials.resolve_profile_host_port` (OPEN-003-A) -- replacing this
    function's own local catalog/host-port read, a divergent copy of the
    same logic `credentials.py`'s own docstring flags as superseded.
    Re-raised as this module's own `ProfileResolutionError` so
    `ensure_raw`'s existing `except ProfileResolutionError` catch (and any
    caller monkeypatching this function directly) keeps working unchanged.

    Precedence note (OPEN-003-A, no partial merge): a profile with a
    `server` catalog key AND only one of `host`/`port` set no longer
    merges the two -- the shared resolver treats explicit `host=`+`port=`
    as an all-or-nothing override and otherwise resolves fully off the
    catalog. Only affects a profile that mixes both forms, which was
    never a documented/supported shape.
    """
    try:
        return credentials.resolve_profile_host_port(profile_name)
    except credentials.ProfileConnectionError as e:
        raise ProfileResolutionError(str(e)) from e


# -- daemon transport -----------------------------------------------------

def send_request(verb, args_payload, *, timeout=15.0, run_dir=None):
    """One connect -> send one JSON line -> read one JSON line -> close
    round trip against `env.socket_path(run_dir)`. Never raises for an
    expected failure mode -- always returns a dict, `{"ok": False,
    "error": ...}` on any transport problem."""
    sock_path = env.socket_path(run_dir)
    if not sock_path.exists():
        return {"ok": False, "error": "daemon_not_running"}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(sock_path))
        payload = json.dumps({"verb": verb, "args": args_payload}) + "\n"
        s.sendall(payload.encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    except OSError as e:
        return {"ok": False, "error": f"connect_failed:{e}"}
    finally:
        s.close()
    if not buf:
        return {"ok": False, "error": "empty_response"}
    try:
        return json.loads(buf.decode("utf-8"))
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"bad_response:{e}"}


def daemon_alive(run_dir=None):
    """True when the pidfile names a process that still exists.

    ``os.kill(pid, 0)`` distinguishes:
    * success / ``PermissionError`` (EPERM) — process **exists** (we may
      lack signal rights); treat as alive so ``ensure`` does not spawn a
      second daemon (single-connection hard rule).
    * ``ProcessLookupError`` (ESRCH) — no such process; treat as absent.
    """
    pid_path = env.pid_path(run_dir)
    if not pid_path.exists():
        return False
    try:
        raw = pid_path.read_text().strip()
    except PermissionError:
        # Pidfile exists but is unreadable — not the same as "no daemon".
        # Conservative: assume held so ensure does not double-spawn.
        return True
    except OSError:
        return False
    try:
        pid = int(raw)
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as e:
        # Some platforms surface ESRCH/EPERM as plain OSError + errno.
        err = getattr(e, "errno", None)
        if err == errno.ESRCH:
            return False
        if err == errno.EPERM:
            return True
        return False


# -- output -----------------------------------------------------------------

def print_response(resp, args):
    if getattr(args, "json", False):
        print(json.dumps(resp))
        return
    if not resp.get("ok"):
        print(f"ERROR: {resp.get('error')}")
        if resp.get("detail"):
            print(f"  detail: {resp['detail']}")
        return
    if "screen" in resp:
        for row in resp["screen"]:
            print(row)
        if not getattr(args, "compact", False):
            bits = []
            if resp.get("prompt"):
                bits.append(f"prompt: {resp['prompt']}")
            if resp.get("classification") or resp.get("class"):
                bits.append(f"class: {resp.get('classification') or resp.get('class')}")
            if resp.get("settled_reason"):
                bits.append(f"settled: {resp['settled_reason']}")
            if bits:
                print("--- " + " | ".join(bits))
    else:
        print(json.dumps(resp, indent=2))


# -- verb implementations ----------------------------------------------------

def cmd_status(args):
    blocked = _guard_run_dir_footgun(args)
    if blocked is not None:
        return blocked
    run_dir = _resolve_run_dir(args.run_dir)
    if not daemon_alive(run_dir):
        resp = {
            "ok": True,
            "daemon_running": False,
            "connected": False,
            # always echo which sock dir this invocation targets (default
            # run/ vs --run-dir), mirrors the archive's status shape.
            "run_dir": str(run_dir),
        }
        print_response(resp, args)
        return 0
    # SESSION-F7 / MT-03: pidfile-alive is not the same as a successful
    # status round-trip (PID reuse / dead sock). Only claim daemon_running
    # when the request itself succeeded.
    resp = send_request("status", {}, run_dir=run_dir)
    ok = bool(resp.get("ok"))
    resp["daemon_running"] = ok
    if not ok:
        resp.setdefault("status_unreachable", True)
    resp["run_dir"] = str(run_dir)
    print_response(resp, args)
    return 0 if ok else 1


def ensure_raw(profile, *, target="main_command", timeout=180.0, no_auto_arm=False, run_dir=None):
    """Core `ensure` implementation shared by `cmd_ensure` (the `tw
    ensure` CLI verb) and `adapters.ensure_session()` (the play-shell's
    Python entry point) -- both need the *same* spawn-then-round-trip
    logic, not two copies that could drift. Returns the daemon's raw
    response dict, or a locally-synthesized `{"ok": False, "error": ...,
    "detail": ...}` dict for a profile/spawn/budget failure that never
    reached the daemon. Never raises for an expected failure mode.

    Bounded by `timeout`: the whole call -- profile resolution, daemon
    spawn-wait, AND the login round trip -- budgets against one monotonic
    deadline, so a daemon that never comes up (or never settles) cannot
    hang the caller past `timeout` seconds. This is the mechanism behind
    canon's "play does not hang past a bounded timeout" contract
    (`canon/architecture/cli-verbs.md`).
    """
    run_dir = run_dir or env.resolve_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)
    env.LOG_DIR.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + timeout

    try:
        host, port = _resolve_profile_connection(profile)
    except ProfileResolutionError as e:
        return {"ok": False, "error": "profile_invalid", "detail": str(e)}

    sock_path = env.socket_path(run_dir)

    if not (daemon_alive(run_dir) and sock_path.exists()):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "error": "timeout", "detail": "budget exhausted before daemon spawn"}

        # WO-ENSURE-STALE-SOCK-RECOVER: orphan `twd.sock` (crashed daemon /
        # leftover live-prove) makes the wait-for-exists loop exit immediately
        # and the settle `read` probe a corpse → `spawn_failed: … never
        # answered`. Unlink before spawn when no live daemon holds the
        # pidfile; do not treat orphan presence as readiness. Pidfile
        # guards unchanged — this branch only runs when `daemon_alive` is
        # already False.
        if sock_path.exists():
            try:
                unlink = getattr(sock_path, "unlink", None)
                if callable(unlink):
                    unlink()
            except OSError:
                pass

        daemon_log_path = run_dir / "twd.stderr.log"
        try:
            daemon_log = open(daemon_log_path, "ab")
        except OSError as e:
            return {"ok": False, "error": "spawn_failed", "detail": f"cannot open {daemon_log_path}: {e}"}

        # WO-P2-020 daemon-spawn idiom: module invocation (there is no
        # `twd` launcher script in the one-tree layout yet -- ADR-001).
        # Confirmed against Monk-D's landed daemon: `twd`'s argv is ONLY
        # `--host/--port/--name` -- it does NOT reimplement run-dir/log-dir
        # flags (WO-P2-021 design: the daemon resolves its run-dir the same
        # way every other module does, via `env.resolve_run_dir()`/
        # `TW_RUN_DIR`, never a CLI override). So the run-dir this spawn
        # must land the daemon's socket in is passed through the
        # subprocess **environment**, not argv -- the same `TW_RUN_DIR`
        # override `env.py` already honors for every caller.
        cmd = [
            sys.executable, "-m", "tw2002_aiclient.session.daemon",
            "--host", host,
            "--port", str(port),
        ]
        spawn_env = {**os.environ, env.RUN_DIR_VAR: str(run_dir)}
        try:
            subprocess.Popen(
                cmd,
                cwd=str(env.PROJECT_ROOT),
                env=spawn_env,
                stdout=daemon_log,
                stderr=daemon_log,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as e:
            daemon_log.close()
            return {"ok": False, "error": "spawn_failed", "detail": str(e)}
        daemon_log.close()

        spawn_deadline = deadline  # never wait past the overall budget
        while time.monotonic() < spawn_deadline and not sock_path.exists():
            time.sleep(0.1)
        if not sock_path.exists():
            return {
                "ok": False,
                "error": "spawn_failed",
                "detail": f"daemon failed to start (no socket after {timeout:.0f}s) -- see {daemon_log_path}",
            }

        # Let the fresh connection produce its first settled screen before
        # driving it -- mirrors `tw start`'s post-spawn read. This round
        # trip IS the readiness proof, NOT the `sock_path.exists()` check
        # above: a unix socket FILE exists as soon as `bind()` runs, before
        # anything is `accept()`-ing on it, so file presence proves nothing
        # about whether the daemon can actually answer yet
        # (WO-ENSURE-SPAWN-READINESS). Its result MUST be read and checked --
        # a discarded not-ready answer here used to fall straight through to
        # the real `ensure` round trip below, which met the same not-ready
        # daemon and surfaced `empty_response` to the operator as though a
        # *remote* game server had failed, when the cause was purely local
        # startup timing. Retry the same probe -- budgeted inside the SAME
        # `deadline` used above, never extended -- until it actually
        # succeeds or the budget is gone; cap each attempt so a slow/idle
        # first screen cannot burn the whole budget in one shot
        # (WO-P2-OPS-VERB-B: `read` is live now; previously unknown_verb
        # returned instantly and hid this hazard).
        settle_ok = False
        last_settle_resp = None
        while True:
            remaining = deadline - time.monotonic()
            settle_budget = min(remaining, 5.0)
            if settle_budget <= 0:
                break
            last_settle_resp = send_request(
                "read",
                {"timeout": settle_budget},
                timeout=settle_budget + 5,
                run_dir=run_dir,
            )
            if last_settle_resp.get("ok"):
                settle_ok = True
                break
            time.sleep(0.1)

        if not settle_ok and last_settle_resp is not None:
            # The socket FILE showed up (the exists() gate above passed),
            # but no round trip against it ever succeeded before the budget
            # ran out -- distinguishable from the "no socket at all" branch
            # above (same `spawn_failed` code, different `detail`, matching
            # this function's existing two-cause `spawn_failed` idiom) and
            # never surfaced as the raw `empty_response`/`connect_failed*`
            # wire error a caller would otherwise misread as a remote
            # failure.
            return {
                "ok": False,
                "error": "spawn_failed",
                "detail": (
                    "daemon socket present but never answered a round trip "
                    f"after {timeout:.0f}s -- see {daemon_log_path} "
                    f"(last probe error: {last_settle_resp.get('error')!r})"
                ),
            }

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {"ok": False, "error": "timeout", "detail": "budget exhausted before ensure round trip"}

    return send_request(
        "ensure",
        {"target": target, "profile": profile, "no_auto_arm": bool(no_auto_arm)},
        timeout=remaining + 5,
        run_dir=run_dir,
    )


def cmd_ensure(args):
    blocked = _guard_run_dir_footgun(args)
    if blocked is not None:
        return blocked
    run_dir = _resolve_run_dir(args.run_dir)
    resp = ensure_raw(
        args.profile,
        target=args.target,
        timeout=args.timeout,
        no_auto_arm=args.no_auto_arm,
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_screen(args):
    """WO-P2-OPS-VERB-A: current settled screen (read-only; never sends)."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request("screen", {"raw": bool(args.raw)}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_stop(args):
    """WO-P2-OPS-VERB-A: ask the daemon to shut down (protocol already present)."""
    blocked = _guard_run_dir_footgun(args)
    if blocked is not None:
        return blocked
    run_dir = _resolve_run_dir(args.run_dir)
    if not daemon_alive(run_dir):
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "daemon_running": False, "run_dir": str(run_dir)}))
        else:
            print("daemon not running")
        return 0
    resp = send_request("stop", {}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_do(args):
    """WO-P2-OPS-VERB-B: send input, wait for settle, return the new screen."""
    run_dir = _resolve_run_dir(args.run_dir)
    timeout = float(args.timeout)
    resp = send_request(
        "do",
        {
            "input": args.input,
            "enter": args.enter,
            "secret": bool(args.secret),
            "wait_prompt": args.wait_prompt,
            "timeout": timeout,
        },
        timeout=timeout + 5,
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_send(args):
    """WO-P2-OPS-VERB-B: raw send, no settle wait."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request(
        "send",
        {
            "input": args.input,
            "enter": args.enter,
            "secret": bool(args.secret),
        },
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_read(args):
    """WO-P2-OPS-VERB-B: wait-and-return without sending."""
    run_dir = _resolve_run_dir(args.run_dir)
    timeout = float(args.timeout)
    resp = send_request(
        "read",
        {
            "wait_prompt": args.wait_prompt,
            "timeout": timeout,
        },
        timeout=timeout + 5,
        run_dir=run_dir,
    )
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_history(args):
    """WO-P2-OPS-VERB-C: recent verb/prompt history from the live session ring."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request("history", {"n": int(args.n)}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_log(args):
    """WO-WIRE-CLI-LOG-TRAIL-VERB: render the trace ledger as a trail.

    Daemon-free filesystem read of ``state/ledger.jsonl`` (override with
    ``--ledger``). ``tw trail`` is the same handler. Never sends; never
    chooses a live keystroke — the ledger is teach/measure only
    (``canon/engine/trace-ledger.md``).
    """
    from tw2002_aiclient.ledger import (
        DEFAULT_LEDGER_PATH,
        read_entries,
        render_trail_line,
    )

    path = getattr(args, "ledger", None)
    world_id = getattr(args, "world_id", None)
    try:
        n = int(getattr(args, "n", 20))
    except (TypeError, ValueError):
        n = 20
    if n < 0:
        n = 0
    entries = read_entries(path, world_id=world_id)
    slice_ = entries[-n:] if n else []
    resolved = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    if getattr(args, "json", False):
        print(
            json.dumps(
                {"ok": True, "path": str(resolved), "entries": slice_},
                ensure_ascii=False,
                default=str,
            )
        )
        return 0
    for entry in slice_:
        print_tty(render_trail_line(entry))
    return 0


def cmd_report(args):
    """WO-BUILD-POST-SESSION-ACTION-REPORT: app-action digest from the ledger.

    Daemon-free filesystem read. Emphasizes ``actor=app`` rows for post-session
    accountability. Never sends. Optional ``--out`` writes the same text to a
    file artifact.
    """
    from tw2002_aiclient.session_report import (
        build_session_report,
        format_session_report,
        write_session_report,
    )

    report = build_session_report(
        path=getattr(args, "ledger", None),
        session_id=getattr(args, "session_id", None),
        world_id=getattr(args, "world_id", None),
        include_interrupted=bool(getattr(args, "include_interrupted", False)),
    )
    text = format_session_report(report)
    out = getattr(args, "out", None)
    if out:
        write_session_report(report, out)
    if getattr(args, "json", False):
        payload = {
            "ok": True,
            "session_id": report.session_id,
            "ledger_path": report.ledger_path,
            "human_count": report.human_count,
            "skipped_interrupted": report.skipped_interrupted,
            "notes": list(report.notes),
            "app_actions": [
                {
                    "ts": r.ts,
                    "screen": r.screen,
                    "rule_id": r.rule_id,
                    "target_player": r.target_player,
                    "input_summary": r.input_summary,
                    "session_id": r.session_id,
                }
                for r in report.app_actions
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    print_tty(text)
    return 0


def cmd_watch(args):
    """WO-P2-OPS-VERB-E2: tail the settle-edge push-stream (read-only).

    Opens a lifetime ``subscribe`` connection — never sends game input.
    ``--frames N`` exits after N *parsed* events (transcript-friendly);
    unparseable lines are reported and do not count toward N. Otherwise
    runs until Ctrl-C / disconnect. SIGINT closes the socket cleanly.
    """
    run_dir = _resolve_run_dir(args.run_dir)
    sock_path = env.socket_path(run_dir)
    if not sock_path.exists():
        print("ERROR: daemon_not_running")
        return 1
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(sock_path))
        s.sendall((json.dumps({"verb": "subscribe", "args": {}}) + "\n").encode("utf-8"))
    except OSError as e:
        print(f"ERROR: connect_failed:{e}")
        s.close()
        return 1
    f = s.makefile("rb")
    count = 0
    try:
        while True:
            line = f.readline()
            if not line:
                break
            try:
                event = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                # SESSION-F8 / MT-04: do not silently swallow corruption —
                # operator-visible tell; --frames still counts only parsed.
                print("ERROR: watch_frame_unparseable", file=sys.stderr)
                continue
            print_response(event, args)
            count += 1
            if args.frames is not None and count >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            f.close()
        except OSError:
            pass
        s.close()
    return 0


def cmd_menumap(args):
    """WO-P2-OPS-VERB-G1: read-only menu-map inspector (coverage / orphans /
    you-are-here). Never sends. Localizes the live screen when a daemon is up.

    Optional ``--to SIG`` runs ``plan_nav`` against the live screen (dry
    keystroke plan by default — never sends). Needs a successful localize;
    without a live look the verb refuses the plan rather than inventing a
    route from store-only state.

    ``--exec --arm`` (both required) runs ``menu_nav_exec.run_nav`` against
    the planned steps via daemon ``do``/``screen``. Without ``--arm``,
    ``--exec`` refuses with zero sends (fail-closed antifire).

    The you-are-here line has THREE states, not two, because "we looked and
    you are not on the map" and "we never managed to look" are different
    facts and the operator can act on only one of them:

    * ``here ★ <label>`` -- localized.
    * ``here off-map``   -- ``localize()`` ran and returned None. Canon's
      escalate-don't-navigate-blind signal, and the ONLY case entitled to
      this line.
    * ``here ? <reason>`` -- the lookup never happened: no daemon, an
      unusable ``screen`` response, a blank screen, or a raised lookup.

    The exit code stays 0 for the three here-states when ``--to`` is absent:
    the map report itself succeeded. With ``--to``, exit is 0 only when the
    plan is ``ok`` (already-there counts as ok with empty steps).
    """
    from tw2002_aiclient.menu import knowledge as menu_knowledge
    from tw2002_aiclient.menu.map_view import (
        format_menu_map_report,
        menu_map_summary_from_store,
    )
    from tw2002_aiclient.menu.nav import localize, plan_nav

    path = args.path
    if not path and getattr(args, "world_id", None):
        path = str(menu_knowledge.knowledge_path_for_world(args.world_id))
    if not path:
        print_tty("ERROR: need --path or --world-id")
        return 1

    run_dir = _resolve_run_dir(getattr(args, "run_dir", None))
    current_sig = None
    screen_text = None
    # Why we could not localize, or None once localize actually answered.
    # Every branch below that leaves `current_sig` unset names itself here:
    # four separate ways of FAILING TO LOOK used to render byte-for-byte
    # identically to a genuine "you are off the map", which is a claim about
    # the player's position that none of them established. Canon reserves
    # off-map for localize's own None -- "STOP, escalate, never navigate
    # blind" (canon/engine/menu-map-and-introspection.md §"Examples") -- so the
    # other four get `here ? <reason>` instead.
    here_unknown = None
    if not daemon_alive(run_dir):
        here_unknown = "no daemon (store only)"
    else:
        resp = send_request("screen", {}, run_dir=run_dir)
        if not resp.get("ok"):
            here_unknown = f"screen unavailable: {resp.get('error') or 'unknown error'}"
        else:
            screen_text = "\n".join(resp.get("screen") or [])
            if not screen_text.strip():
                # The 4th path, undocumented before this WO: daemon up, the
                # `screen` verb ok, but nothing on the screen to localize --
                # `localize` is never called, so it never said off-map.
                here_unknown = "screen is blank"
                screen_text = None
            else:
                try:
                    node = localize(screen_text, path)
                except (OSError, ValueError, TypeError, KeyError) as e:
                    here_unknown = f"lookup failed: {type(e).__name__}"
                else:
                    if node:
                        current_sig = node.get("signature")
                    # else: localize really did answer None. That IS off-map,
                    # the one case that has always been entitled to say so --
                    # `here_unknown` stays None.

    try:
        summary = menu_map_summary_from_store(
            path, current_sig=current_sig, here_unknown=here_unknown
        )
    except (OSError, ValueError, TypeError, KeyError, menu_knowledge.GameKnowledgeError) as e:
        print_tty(f"ERROR: {e}")
        return 1

    to_sig = getattr(args, "to_sig", None)
    plan = None
    if to_sig:
        if here_unknown is not None or screen_text is None:
            reason = here_unknown or "no live screen"
            print_tty(f"ERROR: cannot plan_nav ({reason})")
            return 1
        plan = plan_nav(screen_text, to_sig, path)

    want_exec = bool(getattr(args, "exec_nav", False))
    armed = bool(getattr(args, "arm_nav", False))
    exec_result = None
    if want_exec:
        if not to_sig:
            print_tty("ERROR: --exec requires --to SIG")
            return 1
        if not armed:
            print_tty("ERROR: --exec requires --arm (refuse unarmed; zero sends)")
            return 1
        if plan is None or not plan.get("ok"):
            print_tty(
                f"ERROR: cannot exec_nav ({(plan or {}).get('reason') or 'no plan'})"
            )
            return 1
        from tw2002_aiclient.menu_nav_exec import run_nav

        session = _MenumapNavSession(run_dir)
        exec_result = run_nav(
            session,
            plan,
            path,
            should_abort=lambda: False,
            is_armed=lambda: True,  # --arm already gated above
        )

    if getattr(args, "json", False):
        # JSON stays raw Unicode (machine codecs); operator text lines go
        # through print_tty so ★ / — / · never silent-drop on ASCII TTYs.
        payload = {"ok": True, "path": path, **summary}
        if plan is not None:
            payload["plan"] = plan
            payload["ok"] = bool(plan.get("ok"))
        if exec_result is not None:
            payload["exec"] = {
                "ok": exec_result.ok,
                "outcome": exec_result.outcome,
                "reason": exec_result.reason,
                "sends_issued": exec_result.sends_issued,
                "steps_done": exec_result.steps_done,
            }
            payload["ok"] = bool(exec_result.ok)
        print(json.dumps(payload))
        if exec_result is not None:
            return 0 if exec_result.ok else 1
        if plan is not None and not plan.get("ok"):
            return 1
        return 0
    for line in format_menu_map_report(summary):
        print_tty(line)
    if plan is not None:
        if plan.get("ok"):
            steps = plan.get("steps") or []
            if not steps:
                print_tty(f"plan: already at {to_sig}")
            else:
                print_tty(f"plan: {len(steps)} step(s) -> {to_sig}")
                for step in steps:
                    key = step.get("key")
                    dest = step.get("to_node")
                    kind = step.get("kind") or "?"
                    print_tty(f"  [{kind}] {key!r} -> {dest}")
        else:
            print_tty(f"plan: failed ({plan.get('reason') or 'unknown'})")
            return 1
    if exec_result is not None:
        if exec_result.ok:
            print_tty(
                f"exec: completed ({exec_result.sends_issued} send(s))"
            )
            return 0
        print_tty(
            f"exec: {exec_result.outcome}"
            f" ({exec_result.reason or 'unknown'};"
            f" sends={exec_result.sends_issued})"
        )
        return 1
    return 0


class _MenumapNavSession:
    """Daemon adapter for ``menu_nav_exec.run_nav`` (send + rendered_text)."""

    def __init__(self, run_dir) -> None:
        self._run_dir = run_dir

    def send(self, payload: str) -> None:
        # Menu single-keys: no trailing Enter (same as crawl chokepoint).
        enter = payload == ""
        resp = send_request(
            "do",
            {
                "input": payload,
                "enter": enter,
                "secret": False,
                "timeout": 8.0,
            },
            timeout=13.0,
            run_dir=self._run_dir,
        )
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "do failed")

    def rendered_text(self) -> str:
        resp = send_request("screen", {}, run_dir=self._run_dir)
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error") or "screen failed")
        return "\n".join(resp.get("screen") or [])


def cmd_loops(args):
    """WO-P2-G3: read-only listing of the taught-macro ("learned loop") store.

    Daemon-free by canon -- ``canon/architecture/cli-verbs.md §"The One-Round-Trip Contract"`` lists
    ``loops`` among the reads that "read on-disk artifacts directly, so they
    work with the daemon stopped". So there is no socket round trip here and
    no ``--run-dir``: nothing this verb reports comes from the session, and a
    run-dir flag would imply the listing depends on which daemon is up.

    Deliberately thin. ``loops/store.read_loop_store`` decides what is TRUE
    and ``loops/list_view.format_loops_report`` decides how it READS; this
    function chooses only the exit code. No store logic lives here -- a
    second opinion about what an empty store means is exactly the drift the
    engine-first split exists to prevent, and the in-TUI Learned-Loops
    Library is meant to share the same composer.

    Exit code -- the one decision this wire makes, and it follows the
    reader's ``status``, never the row count:

    * ``unreadable`` -> **1**. Nothing was established, so a scripted caller
      must never be able to read "no loops" out of a store nobody could
      read; ``tw loops || echo none`` is the shape that would otherwise lie
      silently.
    * ``partial``    -> **0**. The listing genuinely succeeded for the
      documents it could read: the rows are real, and the report already
      carries INCOMPLETE plus a named reason per failure -- strictly more
      than an exit code can carry.
    * ``ok`` (populated, empty, or never-written) -> **0**.

    Canon does not rule on that mapping (``cli-verbs.md``'s catalog stops at
    args and actor-class), so it is an evaluator UX call, recorded here so a
    later canon ruling has something explicit to overturn. It matches
    ``cmd_menumap``'s shape: non-zero when the report itself failed, zero
    when only a part of it is unavailable AND says so on the surface.

    Drafts are inert until a human promotes them
    (``canon/engine/candidate-mining.md``), so they are consulted only on
    explicit ``--include-drafts``, and the composer prefixes every draft row
    ``[DRAFT]`` so an inert proposal can never read as an armed macro.
    """
    from tw2002_aiclient.loops.list_view import format_loops_report
    from tw2002_aiclient.loops.store import read_loop_store

    result = read_loop_store(
        include_drafts=bool(getattr(args, "include_drafts", False)),
        world_id=getattr(args, "world_id", None),
    )

    if getattr(args, "json", False):
        # The reader's result verbatim. No ``ok: True`` is synthesized over
        # it: ``cmd_menumap`` can carry that flag because its report either
        # builds or errors out, but here a success flag sitting next to
        # ``status: partial``/``unreadable`` is the exact claim the verb did
        # not earn. ``status`` is the field a caller branches on -- and it
        # has to, because ``loops: []`` is structurally identical for an
        # empty store and an unreadable one.
        print(json.dumps(result))
    else:
        for line in format_loops_report(result):
            print_tty(line)
    return 1 if result.get("status") == "unreadable" else 0


def cmd_pairs(args):
    """WO-CHAIN-DETECT-WIRE Accept 5 (re-scoped 2026-07-28): read-only
    listing of class-derived DISCOVERED pair loops for a world -- the
    thin product caller the WO's typed API requires.

    Daemon-free, world-model-scoped read, same family as ``loops`` above:
    ``chain_detect.recompute`` reads ``state/world/<world_id>/`` directly
    and never opens the daemon socket. Deliberately thin, same split
    discipline as ``cmd_loops``: ``chain_detect.recompute`` decides what
    pairs exist (and, when none do, WHY not -- one of five typed
    reasons); ``chain_detect_view.format_candidate_pair_lines`` decides
    how that reads; this function chooses only the JSON/text branch. No
    store/formatting logic lives here.

    Exit code is always **0** -- every one of the five typed empty
    reasons is a successfully-established fact about the world (``ok,
    nothing found, and here is why``), never a failure to read anything,
    so none of them earns ``cmd_loops``'s ``unreadable -> 1`` treatment.

    NEVER the taught arm list, and never curses: this lists discovered,
    unpriced pair candidates the operator has not taught and cannot arm
    from here (pairs are not displayed in the ``L)chains`` modal either --
    its WO-CHAINS-TUI-FULL discovered section carries N-port
    ``chain_search`` rows only) -- see ``chain_detect_view``'s own module
    docstring for why conflating armable and discovered is exactly the
    mistake this WO exists to prevent.
    """
    from dataclasses import asdict

    from tw2002_aiclient import chain_detect, chain_detect_view

    result = chain_detect.recompute(args.world_id)

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "world_id": result.world_id,
                    "pairs": [asdict(p) for p in result.pairs],
                    "reason": result.reason,
                    "detail": result.detail,
                }
            )
        )
    else:
        for line in chain_detect_view.format_candidate_pair_lines(result):
            print_tty(line)
    return 0


def cmd_chains(args):
    """WO-CHAIN-NPORT-WIRE: read-only listing of DISCOVERED N-port profit
    cycles for a world -- the product caller for the chain finder that had
    shipped complete, tested, and callerless since before the rebirth.

    Sibling of ``pairs`` above, not a replacement: ``pairs`` lists 2-port
    class-derived loops (``chain_detect``); this lists general N-port cycles
    found by real DFS over priced hops (``chain_search`` ->
    ``trade_adapter.build_trade_hops`` -> ``chains.find_profit_chains``).
    A pair is the cheapest shape; a chain is the general one.

    Daemon-free, world-model-scoped read, same family as ``loops``/``pairs``:
    reads ``state/world/<world_id>/`` directly and never opens the daemon
    socket. Deliberately thin, same split discipline: ``chain_search.recompute``
    decides what cycles exist (and, when none do, WHY not -- one of three
    typed reasons, plus whether the search was even exhaustive);
    ``chain_search_view.format_profit_chain_lines`` decides how that reads;
    this function chooses only the JSON/text branch.

    Exit code is always **0** -- every typed empty reason is a successfully
    established fact about the world, never a failure to read anything.

    The JSON branch carries ``adapter_note`` and ``search_note`` as SEPARATE
    fields, and a ``truncated`` boolean. They are different claims -- "I did
    not consider every hop" vs "I did not finish searching the hops I had" --
    and a machine consumer that cannot tell an exhaustive empty from a
    truncated one will report "no profitable cycle exists" when all that
    happened is the budget ran out.

    NEVER the recorded-macro arm list, and never curses: this verb is a
    read-only discovery view and cannot arm or send. ADR-003 gives the
    ``L)chains`` modal a separate exact-fingerprint approve/confirm path;
    it does not turn this CLI output into execution authority.
    """
    from dataclasses import asdict

    from tw2002_aiclient import chain_search, chain_search_view

    result = chain_search.recompute(args.world_id)

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "world_id": result.world_id,
                    "chains": [asdict(c) for c in result.chains],
                    "reason": result.reason,
                    "detail": result.detail,
                    "adapter_note": result.adapter_note,
                    "search_note": result.search_note,
                    "truncated": result.truncated,
                }
            )
        )
    else:
        for line in chain_search_view.format_profit_chain_lines(result):
            print_tty(line)
    return 0


def cmd_record(args):
    """WO-P2-G4-X6: write a taught macro from an already-captured
    demonstration manifest. Daemon-free by design -- no ``--run-dir``, the
    same posture as ``cmd_loops``/``cmd_menumap --path``: everything this
    verb needs is already in the manifest, so there is no socket round trip
    here at all.

    **What this verb is, and what it deliberately is not.** The recorder
    module (``tw2002_aiclient.loops.recorder``) is capture-only and cannot
    send a keystroke -- proven in ``tests/test_loop_recorder.py``. This
    verb does not change that: it never opens a daemon socket, never
    presses a key, and never touches ``protocol.py``/``daemon.py``. It reads
    a MANIFEST -- a JSON document describing a demonstration that has
    ALREADY happened, assembled from real ``tw do``/``tw screen --json``
    output -- and turns it into a stored loop.

    Wiring a live ``tw attach`` session directly into this recorder (so an
    operator presses keys once, live, and the macro falls out the other
    end) is real, useful follow-up work this WO's Scope explicitly excludes
    ("NOT... the daemon") -- it would touch the control-lock/driving-dispatch
    machinery X3/X4 own. Attach keystrokes *do* land in the Trace-Ledger now
    (WO-DAEMON-LEDGER-WRITER-ATTACH / #353), but the recorder still does not
    consume them into a macro. Until a follow-up bridges ledger→recorder,
    the recipe is::

        tw screen --json > anchor.json     # BEFORE the first keystroke
        tw do 'P' --json > step0.json      # for each step, in order
        tw do '' --json > step1.json
        # then assemble the manifest below from each response's own
        # "screen" field (by hand, or with a small script).

    Manifest shape::

        {
          "name": "ore-run",
          "anchor": {"screen": [...]},          # a real response's "screen"
                                                 # field, taken BEFORE step 0
          "steps": [
            {"input": "P", "screen": [...]},
            {"input": "1", "screen": [...], "confirm_exact": true}
          ]
        }

    ``confirm_exact`` (optional, default false) asks the recorder to capture
    that step's resulting prompt line as an exact (escaped) ``wait_prompt``
    -- see ``loops/recorder.py``'s docstring, trap 2.

    Exit codes mirror ``cmd_loops``'s posture: a malformed manifest, or a
    refusal from the recorder itself (no readable start_anchor, an empty
    recording, an unusable name), is reported and this returns 1; a written
    loop returns 0.
    """
    from tw2002_aiclient.loops.recorder import LoopRecorder, RecorderError

    manifest_path = Path(args.manifest)
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: could not read manifest {manifest_path}: {e}")
        return 1
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: manifest is not valid JSON: {e}")
        return 1
    if not isinstance(manifest, dict):
        print("ERROR: manifest top level must be a JSON object")
        return 1

    anchor = manifest.get("anchor")
    anchor_screen = anchor.get("screen") if isinstance(anchor, dict) else None
    steps = manifest.get("steps")
    if not isinstance(steps, list) or not steps:
        print("ERROR: manifest 'steps' must be a non-empty list")
        return 1

    blessed = not bool(getattr(args, "draft", False))
    try:
        recorder = LoopRecorder(manifest.get("name"), anchor_screen)
        for index, raw_step in enumerate(steps):
            if not isinstance(raw_step, dict):
                print(f"ERROR: step {index} is not a JSON object")
                return 1
            recorder.step(
                raw_step.get("input", ""),
                raw_step.get("screen"),
                confirm_exact=bool(raw_step.get("confirm_exact", False)),
            )
        path = recorder.save(
            blessed=blessed,
            world_id=getattr(args, "world_id", None),
        )
    except (RecorderError, TypeError) as e:
        print(f"ERROR: {e}")
        return 1

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "ok": True,
                    "name": recorder.name,
                    "path": str(path),
                    "steps": len(recorder.steps),
                    "draft": not blessed,
                }
            )
        )
    else:
        kind = "draft (inert)" if not blessed else "blessed"
        print_tty(f"recorded {recorder.name!r} -> {path} ({len(recorder.steps)} steps, {kind})")
    return 0


def cmd_explore_start(args):
    """WO-EXPLORE-CLI-INVOKE: start sector explorer for a world."""
    run_dir = _resolve_run_dir(args.run_dir)
    payload: dict = {"world_id": args.world_id}
    if args.min_sectors is not None:
        payload["min_sectors"] = args.min_sectors
    if args.turn_budget is not None:
        payload["turn_budget"] = args.turn_budget
    # Always sent, unlike the two above: CLI and daemon both default OFF
    # (WO-EXPLORE-DOCK-DEFAULT-OFF); omitting would still be False today but
    # sending keeps an explicit arm decision on the wire.
    payload["dock_new_ports"] = bool(getattr(args, "dock_new_ports", False))
    payload["fight_tolls"] = bool(getattr(args, "fight_tolls", False))
    # WO-FORMATIONS-CATALOG-PORT: opt-in intent; omitted → daemon default map_fill.
    intent = getattr(args, "intent", None)
    if intent:
        payload["intent"] = intent
    resp = send_request("explore_start", payload, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_explore_stop(args):
    """WO-EXPLORE-CLI-INVOKE: stop the running sector explorer."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request("explore_stop", {}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_explore_status(args):
    """WO-EXPLORE-CLI-INVOKE: query sector explorer status."""
    run_dir = _resolve_run_dir(args.run_dir)
    resp = send_request("explore_status", {}, run_dir=run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


def cmd_reflex(args):
    """WO-REFLEX-CLIENT-REACH: what the taught rule library PROPOSES, read-only.

    Goes through ``send_request`` directly rather than
    ``adapters.reflex_propose``, which is the house pattern -- every other
    ``cmd_*`` here does the same, and ``adapters`` imports *this* module, so
    calling upward would invert the dependency. (Measured, not assumed: the
    resulting cycle does import cleanly today, because neither module touches
    the other's attributes at import time. It is tolerated rather than broken,
    which is exactly the kind that breaks later, and there is no reason to
    introduce one to satisfy a layering nobody needs. ``adapters`` remains the
    path for *importers*; this is the path for the CLI.)

    **A proposal is not an act.** The wording below is deliberate: this prints
    what the library *would suggest*, and nothing about arming or running it.
    The taught run path still requires the human's ``y`` at arm-confirm, and
    an approved rule proposing a macro that reaches a money prompt still
    halts on ``never_auto_action``.

    A STOP is a **successful answer**, exit 0. Only a transport failure is
    exit 1. Rendering "the library says do nothing" as an error would train
    an operator to ignore the one channel that reports a real refusal --
    and today, with no rule writer shipped, `autopilot_no_candidates` is the
    *normal* answer on every install.
    """
    run_dir = _resolve_run_dir(args.run_dir)
    arming = bool(getattr(args, "arm", False))
    if arming and getattr(args, "json", False):
        # Refused rather than resolved either way. `--json` returns before the
        # prompt, so honouring both would print a preview and silently not arm
        # -- a surface agreeing to something it does not do. And a
        # machine-readable arm flow is the scriptable confirmation this WO
        # exists to prevent, so the pair is refused rather than ordered.
        print("ERROR: --arm cannot be combined with --json")
        return 1
    resp = send_request("reflex", {}, run_dir=run_dir)
    if getattr(args, "json", False):
        print(json.dumps(resp))
        return 0 if resp.get("ok") else 1
    if not resp.get("ok"):
        print(f"ERROR: {resp.get('error')}")
        if resp.get("detail"):
            print(f"  detail: {resp['detail']}")
        return 1
    block = resp.get("reflex")
    block = block if isinstance(block, dict) else {}
    klass = resp.get("classification") or "unknown"
    print(f"screen: {klass}")
    macro = block.get("macro")
    if macro:
        rule_id = block.get("rule_id") or "?"
        # "would run" / "proposes", never "running" or "armed".
        print(f"proposes: {macro}  (rule {rule_id})")
        if not arming:
            # Suppressed only under `--arm`, where the very next line asks the
            # question this sentence says has not been asked.
            print("not armed — this is a suggestion; arming is still your 'y' at arm-confirm")
    else:
        reason = block.get("stop_reason") or "no proposal"
        print(f"proposes: nothing  ({reason})")
    if arming:
        # Local import for `rules/cli.py`'s reason: this module is already
        # over the line cap with #218 frozen, and the arm flow is worth
        # calling from a test without argparse or a socket.
        from ..rules.arm import run_arm_flow

        return run_arm_flow(
            block,
            # The RAW classification, never the `klass` display fallback
            # above: sending "unknown" would claim the human confirmed a
            # screen class the daemon never reported. An absent class must
            # reach the flow as absent so it can refuse to ask at all.
            resp.get("classification"),
            launch=lambda payload: send_request("reflex_arm", payload, run_dir=run_dir),
        )
    return 0


def _arm_lossless_stdin():
    """Make ``sys.stdin`` park an undecodable byte as a PEP 383 surrogate
    instead of raising, and report whether stdin is now lossless.

    ``cmd_attach`` forwards the operator's keystrokes to an **8-bit** game
    wire, so every byte the terminal delivers is potentially meaningful --
    but ``sys.stdin`` decodes to ``str`` first, under whatever codec the
    ambient locale picked, and a *strict* handler turns a byte it cannot
    decode into a ``UnicodeDecodeError``. Measured, not assumed: that error
    also discards the rest of the chunk the wrapper had already read, so a
    ``0xFF`` typed just before ``Q`` loses BOTH -- catching the exception and
    continuing would silently eat keystrokes, which is the exact class of
    harm this whole verb keeps being fixed for. Preventing the error is the
    only honest option, so we ask for ``surrogateescape`` up front.

    ``reconfigure()`` is only legal before the stream's first read, which is
    why this is called before the cbreak loop and nowhere else. It is a
    no-op when stdin already decodes with ``surrogateescape`` (the default
    on a UTF-8 or coerced-C locale), and it returns False rather than
    raising for a stdin that cannot be reconfigured at all -- a test double,
    or a stream something upstream already read. ``io.UnsupportedOperation``
    subclasses both ``ValueError`` and ``OSError``, so it needs no import
    here; ``TypeError`` covers a double with an incompatible signature.
    """
    stream = sys.stdin
    if getattr(stream, "errors", None) == "surrogateescape":
        return True
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return False
    try:
        reconfigure(errors="surrogateescape")
    except (TypeError, ValueError, OSError):
        return False
    return getattr(stream, "errors", None) == "surrogateescape"


def cmd_attach(args):
    """WO-P2-OPS-VERB-F1: take control_lock and forward keystrokes (thin).

    No curses screen paint yet (F2 spectate). Interactive mode needs a TTY
    (cbreak until Ctrl-], EOF, or a failed send). ``--keys`` sends latin-1
    bytes then detaches -- for FakeDaemon / scripted proof without a TTY.

    The exit code is honest about delivery on BOTH paths: a ``send_key()``
    returning False ends the session and returns 1 rather than continuing
    to swallow the pilot's keystrokes behind an ``ATTACHED`` banner
    (interactive: WO-AUDIT-ATTACH-SEND-KEY-BOOL; scripted ``--keys``:
    WO-AUDIT-CLI-KEYS-IGNORE-RETURN).

    Non-delivery is therefore reported in TWO different registers, because
    there are two different conditions and only one of them is fatal:

    * **transport failure** (``send_key()`` -> False) -- the wire is dead,
      nothing further will get through: report and END the session, rc 1.
    * **unencodable key** (interactive only) -- the wire is fine, but that
      character has no 8-bit encoding for the game: report and KEEP GOING,
      rc still 0 on a clean detach. Nothing is put on the wire for it.

    So on the interactive path rc 0 means "nothing was dropped by the
    transport", not "every key you pressed reached the game" -- an
    unencodable key is reported inline, at the moment it happens, which is
    the only surface the operator has here (thin attach paints no screen).

    ``--keys`` takes the FIRST register, not the second: an unencodable key
    there is rc 1, because there is no live session to protect and a script
    must be able to detect non-arrival. Nothing is sent at all in that case
    -- a partial send would put DIFFERENT bytes on the wire than were asked
    for, which is worse than sending none.

    Two properties this function holds deliberately, both easy to break by
    accident and both pinned by test:

    * **Every operator-facing string here is pure ASCII.** This is the one
      code path whose whole subject is a terminal that cannot represent
      some character, and it is reached on exactly the 8-bit and ascii
      terminals where a non-ASCII byte in our OWN output raises
      ``UnicodeEncodeError`` and kills the verb. The banner used to carry
      an em-dash and did precisely that on a latin-1 or ascii stdout: the
      operator lost attach before they could press a key, while the
      carefully-ASCII refusal notice thirty lines below never got to fire.
      An ASCII-only rule for the whole function is the property; a
      hand-checked line is not.
    * **A byte the terminal could not decode is still delivered.** See
      ``_arm_lossless_stdin`` and the surrogate branch in the loop.
    """
    from .attach_client import DETACH_KEY, AttachInputConn

    run_dir = _resolve_run_dir(args.run_dir)
    sock_path = env.socket_path(run_dir)
    if not sock_path.exists():
        print("ERROR: daemon_not_running")
        return 1

    keys = getattr(args, "keys", None)
    if keys is None and not sys.stdin.isatty():
        print("ERROR: tw attach needs a real terminal (or pass --keys for scripted use)")
        return 1

    conn = AttachInputConn(sock_path)
    if not conn.connect():
        print(f"ERROR: {conn.error or 'attach_failed'}")
        return 1

    try:
        if keys is not None:
            # Scripted: interpret escapes lightly -- \r \n \xNN and raw chars
            # (the contract README.md documents for this flag).
            #
            # THE ROOT DEFECT WAS NOT A DROP, IT WAS A DOUBLE ENCODE. The old
            # chain began `keys.encode("utf-8")`, and `unicode_escape` is a
            # LATIN-1-based codec: it decodes each BYTE to one codepoint. So a
            # UTF-8 multi-byte sequence came back as one character per byte,
            # every one of them latin-1-representable, and the final encode
            # shipped them all. `errors="ignore"` therefore almost never
            # fired -- the branch was not dropping non-ASCII input, it was
            # MANGLING it, silently, with rc 0:
            #
            #     --keys with a raw U+00FF  ->  wire b"\xc3\xbf"   (two bytes)
            #     the same key interactively ->  wire b"\xff"     (one byte)
            #
            # One character asked for, two bytes delivered, and the two halves
            # of the same verb disagreeing about a byte class an 8-bit
            # TradeWars wire is made of. Fixing only the visible drops would
            # have left every non-ASCII `--keys` value still going out as
            # mojibake -- a fix that passes its own tests while the real bug
            # runs on.
            #
            # So the FIRST encode is `latin-1`, not `utf-8`: encode the
            # operator's characters to the 8-bit bytes the game wire actually
            # takes, and hand `unicode_escape` the operator's OWN bytes
            # instead of a UTF-8 re-encoding of them. `unicode_escape` stays,
            # because the documented `\r` / `\n` / `\xNN` forms are its whole
            # job -- and it is now correct rather than incidentally lossy,
            # since latin-1 is exactly the code page it decodes back with.
            # The round trip is now an identity on every character the wire
            # can carry.
            #
            # Its `surrogateescape` handler covers the other half: argv
            # reaches Python already decoded by the OS-encoding codec with
            # PEP 383, so a raw 8-bit byte on the command line
            # (`--keys $'\xff'`) arrives as the lone surrogate U+DCFF, and
            # this maps it straight back to its byte. Strict raised
            # UnicodeEncodeError there and killed the verb with an uncaught
            # traceback. Identical recovery to the interactive loop below.
            #
            # The LAST encode is STRICT (it was `errors="ignore"`), which is
            # what makes a genuinely unencodable key visible instead of
            # silent. Both surviving failure shapes exited 0 before:
            #   full drop     `--keys '\u2192'`  -> sent nothing, rc 0,
            #                                       indistinguishable from
            #                                       `--keys ""`
            #   partial drop  `--keys 'a\u2192b'` -> sent b"ab", rc 0 -- not
            #                                       nothing, but DIFFERENT
            #                                       bytes than asked for
            #
            # ONE `except UnicodeEncodeError` covers both encodes deliberately,
            # because they are the same question asked of two populations:
            #   * first encode  -- a RAW character the wire cannot carry
            #                      (`--keys '\u2192'`), which used to be mangled
            #                      into its UTF-8 bytes. `e.start` indexes argv.
            #   * last encode   -- a character an ESCAPE produced. There are
            #                      FOUR such forms, not two (brute-forced, not
            #                      reasoned):
            #                        \uXXXX      -> up to U+FFFF
            #                        \UXXXXXXXX  -> up to U+10FFFF
            #                        \N{NAME}    -> any named codepoint
            #                        \400-\777   -> U+0100-U+01FF  (octal
            #                                      escape overflow)
            #                      `e.start` indexes the escape-DECODED keys.
            # Both hand us the offending index and codepoint for free, which
            # the length comparison originally specified could not have done.
            #
            # A useful consequence of encoding latin-1 FIRST: a backslash
            # immediately before an unencodable character (`--keys 'a\\u2192b'`)
            # is refused at the first encode rather than becoming ambiguous.
            # Nothing here ever manufactures escape text, so nothing can be
            # re-read as an escape the operator did not write.
            #
            # UnicodeDecodeError is the other half, and a different failure:
            # an escape that cannot be decoded AT ALL -- a trailing backslash,
            # or a truncated \x \u \U \N -- which was also an uncaught
            # traceback. Reported in the same register; nothing is sent.
            try:
                data = (
                    keys.encode("latin-1", errors="surrogateescape")
                    .decode("unicode_escape")
                    .encode("latin-1")
                )
            except UnicodeEncodeError as e:
                # Codepoint, never the glyph: same rule and same reasons as
                # the interactive notice below.
                print(
                    f"ERROR: key U+{ord(e.object[e.start]):04X} at index "
                    f"{e.start} has no 8-bit encoding for this game "
                    "connection; nothing was sent"
                )
                return 1
            except UnicodeDecodeError as e:
                # `e.start` here is a BYTE offset into the encoded argv, a
                # different unit from the branch above; named as such rather
                # than blurred into one word for both.
                #
                # `e.reason` and `e.start` ONLY -- never `str(e)` and never
                # `e.object`. Both `UnicodeDecodeError.object` and the
                # analogous `JSONDecodeError.doc` hold the ENTIRE input that
                # failed to parse, and neither is rendered by `str(e)`, so
                # reaching for the whole exception here would quietly widen a
                # one-line diagnostic into an echo of the operator's full
                # `--keys` argument. `e.reason` is a short fixed codec string
                # ("\\ at end of string", "truncated \\uXXXX escape").
                print(
                    f"ERROR: --keys could not be decoded ({e.reason}) at byte "
                    f"index {e.start}; nothing was sent"
                )
                return 1
            # `if data:` is now ONLY the deliberate `--keys ""` pin (032bc12):
            # "you asked for nothing" stays distinguishable from "everything
            # you asked for was thrown away", which is no longer reachable --
            # a dropped character raises above instead of arriving here as an
            # empty payload. Do not "simplify" this away.
            if data:
                if not conn.send_key(data):
                    print("ERROR: send_failed")
                    return 1
            return 0

        import termios
        import tty

        # Before the first read, and before the banner: see
        # `_arm_lossless_stdin`. Its result is deliberately not branched on --
        # a stdin that refuses to become lossless still attaches, and the
        # `UnicodeDecodeError` backstop in the loop below is what covers it.
        _arm_lossless_stdin()

        # PURE ASCII, and it has to stay that way -- this line used to carry
        # an em-dash and killed `tw attach` outright on a latin-1 or ascii
        # stdout, before the operator could press a single key. See the
        # ASCII property in this function's docstring.
        print("ATTACHED -- Ctrl-] detach (thin attach: no live screen paint yet; use tw watch)", flush=True)
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        send_failed = False
        undecodable_stdin = None
        try:
            tty.setcbreak(fd)
            while True:
                try:
                    ch = sys.stdin.read(1)
                except UnicodeDecodeError as e:
                    # BACKSTOP, not the live path: `_arm_lossless_stdin`
                    # above normally makes this unreachable by parking an
                    # undecodable byte as a surrogate instead of raising.
                    # Reached only when stdin could not be reconfigured.
                    #
                    # It ENDS the session rather than continuing, and that is
                    # the honest choice even though a lone bad key is
                    # survivable elsewhere in this loop: measured, a strict
                    # decode error also discards the rest of the chunk the
                    # wrapper had already read, so "report and keep going"
                    # would silently swallow keystrokes the operator had
                    # already typed. Continuing would recreate the exact
                    # defect this verb keeps being fixed for.
                    undecodable_stdin = e
                    break
                if not ch:
                    break
                code = ord(ch)
                if code == DETACH_KEY:
                    break
                if ch in ("\n", "\r"):
                    payload = b"\r\n"
                elif 0xDC80 <= code <= 0xDCFF:
                    # A byte stdin's decoder could NOT decode, parked as a
                    # lone PEP 383 surrogate: U+DC80-U+DCFF *is* byte
                    # 0x80-0xFF, by that PEP's definition. Recover it and
                    # SEND it -- it is deliverable, and it is precisely the
                    # byte class an 8-bit TradeWars wire is made of (an
                    # 8-bit Meta terminal, a latin-1 host, a pasted latin-1
                    # blob). The refusal below used to catch these and name
                    # them "U+DCFF", a codepoint that exists on no keyboard
                    # and that the operator never pressed: wrong twice, once
                    # for refusing a deliverable key and once for the name.
                    #
                    # Unambiguous: a lone surrogate cannot arrive from a
                    # terminal any other way (it has no UTF-8 form), so this
                    # branch cannot capture a character the operator meant
                    # literally. Surrogates outside DC80-DCFF are not
                    # PEP 383 escapes and fall through to the refusal below.
                    payload = bytes([code - 0xDC00])
                else:
                    try:
                        payload = ch.encode("latin-1")
                    except UnicodeEncodeError:
                        # A GENUINE character the game's 8-bit wire cannot
                        # carry (a curly quote, an em-dash, an emoji --
                        # typically pasted, not typed), as opposed to the
                        # undecodable BYTE handled by the branch above, which
                        # is deliverable and is sent.
                        # `errors="ignore"` used to turn it into b"",
                        # which the daemon answered `{"ok": true}`: the
                        # keystroke vanished with every surface reporting
                        # success. Decided HERE, before the wire, because the
                        # client already knows the character is unencodable.
                        #
                        # NOT the `send_failed` path below, deliberately: that
                        # one means the wire is broken and nothing will ever
                        # get through, so ending attach is right. This one
                        # means the wire is FINE and one character cannot be
                        # represented -- ending the session over a pasted
                        # em-dash would be a worse harm than the silent drop,
                        # and the human is the sovereign pilot here
                        # (canon/architecture/north-star.md). So: tell them,
                        # send nothing, keep the keyboard.
                        #
                        # The codepoint is named, never the glyph. cbreak has
                        # ECHO off and this session may be sitting on a game
                        # password prompt, so the keystroke itself may be part
                        # of a secret.
                        #
                        # CITATION CORRECTED: this used to cite canon's "a
                        # refused key is never echoed verbatim". That clause is
                        # real but is about something else entirely -- it lives
                        # in "The Credential Bank -- metadata only (TW-31)" and
                        # governs a rejected notes-dict KEY NAME, not a
                        # keystroke. The clauses that actually govern here are
                        # in the same doctrine (canon/doctrine/secrets-and-
                        # credentials.md): the section "Redaction: the send
                        # path, and its one honest boundary", which extends the
                        # redaction contract to "a raw human keystroke typed
                        # into an interactive attach session that happens to
                        # land on a password prompt"; its Schema row for the TX
                        # raw-byte send channel ("interactive attach
                        # keystroke", redacted, decided fresh at send time);
                        # and the worked Example "A password typed into a live
                        # attach session". The reasoning never changed -- only
                        # the clause it points at, which was wrong.
                        #
                        # Naming the CODEPOINT is safe and stays: any character
                        # reaching this branch is by construction not
                        # latin-1-representable, so it cannot be a byte of a
                        # working password on an 8-bit telnet game. Echoing the
                        # raw glyph back into a raw-mode terminal would be an
                        # independent hazard anyway (combining marks, bidi
                        # overrides).
                        #
                        # ASCII-only, like every other operator string in this
                        # function now is (see the docstring's ASCII property).
                        # This message carries the rule's sharpest case -- it
                        # fires BECAUSE something could not be represented, so
                        # it must not itself depend on the terminal rendering a
                        # non-ASCII character. It also makes "the glyph was not
                        # echoed" a checkable property of the line rather than
                        # a claim.
                        print(
                            f"NOT SENT: key U+{ord(ch):04X} has no 8-bit "
                            "encoding for this game connection (still attached)",
                            flush=True,
                        )
                        continue
                sent_ok = conn.send_key(payload)
                if not sent_ok:
                    # Both send sites feed this ONE check deliberately:
                    # fixing either alone is what left this loop dropping
                    # the pilot's keystrokes while still showing ATTACHED
                    # and exiting 0. Reported below rather than here so
                    # the `finally:` has provably restored the terminal
                    # before the operator reads the line (and so the outer
                    # `finally: conn.close()` still releases the wire).
                    send_failed = True
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if send_failed:
            print("ERROR: send_failed -- keystrokes are NOT reaching the game; attach ended")
            return 1
        if undecodable_stdin is not None:
            # Same "report after the terminal is restored" discipline as
            # send_failed above. Reports the terminal's own codec by name,
            # because that is the thing the operator has to change.
            print(
                f"ERROR: this terminal's input encoding "
                f"({undecodable_stdin.encoding}, strict) cannot carry an "
                "8-bit key; attach ended"
            )
            return 1
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()
    return 0


# -- parser -------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tw",
        description="tw2002-aiclient backend/ops CLI (verb table grows one WO at a time).",
    )
    sub = parser.add_subparsers(dest="verb")

    sp = sub.add_parser(
        "status",
        help="daemon alive? connected? idle-ms? classification? (includes run_dir)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (required when TW_CONFIG_DIR "
                          "isolates config -- config isolation does not move the socket)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser(
        "ensure",
        help=(
            "idempotent auto-login -- the ONE verb a Bash-driving caller invokes: "
            "classifies the current screen, no-ops if already at target, else logs "
            "in using the profile's stored credential, spawning the daemon first "
            "if none is running"
        ),
    )
    sp.add_argument("target", nargs="?", default="main_command",
                     help="target classification (default: main_command)")
    sp.add_argument("--profile", required=True, help="profile name in config/profiles.toml")
    sp.add_argument("--timeout", type=float, default=180.0, help="overall budget for the login automaton")
    sp.add_argument("--no-auto-arm", action="store_true", dest="no_auto_arm",
                     help="accepted no-op: ensure never auto-arms; flag confirms non-arming (symmetry with any future default-arm proposal)")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (required when TW_CONFIG_DIR "
                          "isolates config -- config isolation does not move the socket)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_ensure)

    sp = sub.add_parser(
        "screen",
        help="current settled screen (non-destructive; never sends)",
    )
    sp.add_argument("--raw", action="store_true", help="uncropped pyte grid (session.render_raw)")
    sp.add_argument("--compact", action="store_true",
                     help="omit prompt/class footer after the screen rows")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_screen)

    sp = sub.add_parser(
        "stop",
        help="graceful daemon shutdown (in-game QUIT when at main prompt; else disconnect)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (required when TW_CONFIG_DIR "
                          "isolates config -- config isolation does not move the socket)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser(
        "do",
        help="send input, wait for settle, return the new screen",
    )
    sp.add_argument("input", help="text to send (CRLF appended unless --no-enter)")
    sp.add_argument("--no-enter", action="store_false", dest="enter",
                     help="do not append CRLF after input")
    sp.set_defaults(enter=True)
    sp.add_argument("--secret", action="store_true",
                     help="password entry -- never persisted to the transcript log")
    sp.add_argument("--wait-prompt", default=None, dest="wait_prompt",
                     help="case-sensitive regex; settle waits until prompt matches")
    sp.add_argument("--timeout", type=float, default=8.0, help="settle timeout seconds")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_do)

    sp = sub.add_parser(
        "send",
        help="raw send, no settle wait (rare / low-level)",
    )
    sp.add_argument("input", help="text to send (CRLF appended unless --no-enter)")
    sp.add_argument("--no-enter", action="store_false", dest="enter",
                     help="do not append CRLF after input")
    sp.set_defaults(enter=True)
    sp.add_argument("--secret", action="store_true",
                     help="password entry -- never persisted to the transcript log")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_send)

    sp = sub.add_parser(
        "read",
        help="wait for settle and return the screen without sending",
    )
    sp.add_argument("--wait-prompt", default=None, dest="wait_prompt",
                     help="case-sensitive regex; settle waits until prompt matches")
    sp.add_argument("--timeout", type=float, default=8.0, help="settle timeout seconds")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser(
        "history",
        help="recent screens/commands from the live session history ring",
    )
    sp.add_argument("--n", type=int, default=20, help="max entries to return (default 20)")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_history)

    # WO-WIRE-CLI-LOG-TRAIL-VERB: same handler for `log` and `trail`.
    _log_help = (
        "render the trace ledger as QUESTION -> KEYSTROKE -> RESULT "
        "(filesystem read; daemon not required)"
    )
    for _verb in ("log", "trail"):
        sp = sub.add_parser(_verb, help=_log_help)
        sp.add_argument(
            "--n",
            type=int,
            default=20,
            help="max trail rows to print, most recent (default 20)",
        )
        sp.add_argument(
            "--ledger",
            default=None,
            metavar="PATH",
            help="ledger JSONL path (default: state/ledger.jsonl)",
        )
        sp.add_argument(
            "--world-id",
            default=None,
            dest="world_id",
            metavar="SLUG",
            help="only rows stamped with this world_id",
        )
        sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
        sp.set_defaults(func=cmd_log)

    sp = sub.add_parser(
        "report",
        help=(
            "post-session action report - summarize app-attributed ledger "
            "dispatches (filesystem read; daemon not required)"
        ),
    )
    sp.add_argument(
        "--ledger",
        default=None,
        metavar="PATH",
        help="ledger JSONL path (default: state/ledger.jsonl)",
    )
    sp.add_argument(
        "--session-id",
        default=None,
        dest="session_id",
        metavar="ID",
        help="only rows for this session_id",
    )
    sp.add_argument(
        "--world-id",
        default=None,
        dest="world_id",
        metavar="SLUG",
        help="only rows stamped with this world_id",
    )
    sp.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help="also write the text digest to this path",
    )
    sp.add_argument(
        "--include-interrupted",
        action="store_true",
        help="include app rows marked interrupted_by_human",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser(
        "watch",
        help="tail the settle-edge push-stream (read-only spectator feed)",
    )
    sp.add_argument(
        "--frames",
        type=int,
        default=None,
        metavar="N",
        help="exit after N events (default: run until Ctrl-C)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.add_argument("--compact", action="store_true",
                     help="screen only -- omit prompt/class/settled footer")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser(
        "attach",
        # ASCII, for the same reason cmd_attach's own strings are: `tw attach
        # --help` and `tw --help` both print this line, and on the ascii or
        # latin-1 terminal where attach's encoding behaviour actually matters
        # a non-ASCII glyph here crashes the help output instead. WO-ASCII-
        # ENCODE-HONESTY scrubbed the remaining help/epilog offenders the
        # same way -- format_help() must stay pure ASCII.
        help="take the keyboard (control-lock); thin attach -- no curses paint yet",
    )
    sp.add_argument(
        "--keys",
        default=None,
        metavar="BYTES",
        # Pure ASCII (WO-ASCII-ENCODE-HONESTY): help prints on the same
        # ascii/latin-1 terminals where attach encoding matters. Doctrine
        # draft in secrets-and-credentials.md Invariant 1; KEYS-ARGV stamp.
        help=(
            "scripted keystrokes then detach (unicode-escape; no TTY). "
            "NEVER a password - lands in argv/history"
        ),
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.set_defaults(func=cmd_attach)

    sp = sub.add_parser(
        "menumap",
        help=(
            "menu-map inspector: coverage, dead-ends, orphans, "
            "you-are-here; dry --to plan, or --exec --arm to send"
        ),
    )
    sp.add_argument(
        "--path",
        default=None,
        help="game_knowledge.json path (primary; required unless --world-id)",
    )
    sp.add_argument(
        "--world-id",
        dest="world_id",
        default=None,
        help="world_id slug under state/world/ (joins .../game_knowledge.json)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.add_argument(
        "--to",
        dest="to_sig",
        default=None,
        metavar="SIG",
        help=(
            "plan_nav to this menu-map signature (dry unless --exec --arm; "
            "needs live localize)"
        ),
    )
    sp.add_argument(
        "--exec",
        dest="exec_nav",
        action="store_true",
        help="execute plan_nav steps via menu_nav_exec (requires --to and --arm)",
    )
    sp.add_argument(
        "--arm",
        dest="arm_nav",
        action="store_true",
        help="human arm gate for --exec (without this, --exec refuses with zero sends)",
    )
    sp.set_defaults(func=cmd_menumap)

    sp = sub.add_parser(
        "loops",
        # ASCII, deliberately -- same discipline as attach/menumap help.
        help=(
            "list the learned-loop (taught-macro) store -- names, provenance, "
            "profit metadata; reads state/skills (or --world-id path), never sends"
        ),
    )
    sp.add_argument(
        "--include-drafts",
        action="store_true",
        dest="include_drafts",
        help="also list mined drafts, tagged [DRAFT] (inert until a human promotes them)",
    )
    sp.add_argument(
        "--world-id",
        default=None,
        dest="world_id",
        metavar="SLUG",
        help="world-scoped store under state/world/<slug>/skills (migrates flat on first read)",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_loops)

    sp = sub.add_parser(
        "pairs",
        help=(
            "list class-derived DISCOVERED pair loops for a world -- "
            "reads state/world/<world-id> directly, never sends, never the taught arm list"
        ),
    )
    sp.add_argument(
        "--world-id",
        required=True,
        dest="world_id",
        metavar="SLUG",
        help="world_id slug (state/world/<slug>/)",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_pairs)

    sp = sub.add_parser(
        "chains",
        help=(
            "list DISCOVERED N-port profit cycles for a world -- reads "
            "state/world/<world-id> directly, never sends, never the taught arm list"
        ),
    )
    sp.add_argument(
        "--world-id",
        required=True,
        dest="world_id",
        metavar="SLUG",
        help="world_id slug (state/world/<slug>/)",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_chains)

    sp = sub.add_parser(
        "record",
        help=(
            "write a taught macro from an already-captured demonstration "
            "manifest -- state/skills, daemon-free, never sends"
        ),
    )
    sp.add_argument("manifest", help="path to a JSON capture manifest (see cmd_record's docstring)")
    sp.add_argument(
        "--draft",
        action="store_true",
        help="write to state/skills/_drafts/ (inert) instead of the blessed store",
    )
    sp.add_argument(
        "--world-id",
        default=None,
        dest="world_id",
        metavar="SLUG",
        help="write under state/world/<slug>/skills (migrates flat on first write)",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_record)

    # --- explore sub-group (WO-EXPLORE-CLI-INVOKE) ---
    sp_ex = sub.add_parser(
        "explore",
        help="sector exploration: start|stop|status (routes to daemon explore_* verbs)",
    )
    ex_sub = sp_ex.add_subparsers(dest="explore_verb")

    sp_ex.set_defaults(func=lambda _: (sp_ex.print_help() or 0), run_dir=None, json=False)

    sp = ex_sub.add_parser("start", help="start sector explorer for a world")
    sp.add_argument("--world-id", required=True, dest="world_id", metavar="SLUG",
                    help="world_id slug (state/world/<slug>/)")
    sp.add_argument("--min-sectors", type=int, default=None, dest="min_sectors",
                    help="minimum distinct sectors to visit (default daemon: 5)")
    sp.add_argument("--turn-budget", type=int, default=None, dest="turn_budget",
                    help="maximum turns to spend (default daemon: 50)")
    # WO-EXPLORE-DOCK-DEFAULT-OFF / WO-EXPLORE-DOCK-DIALECT: default OFF.
    # Library default is already False; CLI matches it. Opt-in (turn-spend).
    #
    # The original reason recorded here -- "until a recognizable dock dialect
    # is captured" -- was wrong, and is corrected rather than deleted because
    # it is why this flag spent a release defaulted off for the wrong cause.
    # The menu dialect always matched; #205's live `dock_screen_unrecognized`
    # was sector attribution failing on the post-`T` screen. That is fixed.
    # It stays OFF for a DIFFERENT and larger reason: when the port has goods
    # you can trade, `T` lands in a money dialogue that takes its default on
    # unparsable input, and no observed input leaves it without trading. The
    # run ingests the table and then halts there for the human. Arming it
    # unattended risks both credits and an inactivity disconnect.
    sp.add_argument("--dock-new-ports", action=argparse.BooleanOptionalAction,
                    default=False, dest="dock_new_ports",
                    help="dock first-sight ports to ingest commodities (spends "
                         "one turn each; declines commodity quantities with 0; "
                         "does not trade)")
    # WO-FIGHTER-TOLL-POLICY-WIRE: the combat arm. OFF by default and opt-in
    # per run -- there is no persisted "always fight" setting on purpose, so
    # arming is an explicit decision the operator makes each time.
    sp.add_argument("--fight-tolls", action=argparse.BooleanOptionalAction,
                    default=False, dest="fight_tolls",
                    help="let the toll policy answer fighter encounters "
                         "(Attack/Retreat only, never Pay; OFF by default)")
    # WO-FORMATIONS-CATALOG-PORT: closed set mirrors explore.INTENTS (not
    # ARMABLE_INTENTS — Play E-cycle stays 2-wide; formations is CLI-only).
    from tw2002_aiclient import explore as _explore_intents

    sp.add_argument(
        "--intent",
        choices=sorted(_explore_intents.INTENTS),
        default=None,
        dest="intent",
        help="explore intent (default daemon: map_fill; find_formations is "
             "CLI-armable, not on Play's E cycle)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                    help="daemon run directory override")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_explore_start)

    sp = ex_sub.add_parser("stop", help="stop the running sector explorer")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                    help="daemon run directory override")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_explore_stop)

    sp = ex_sub.add_parser("status", help="query sector explorer status")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                    help="daemon run directory override")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_explore_status)

    # WO-REFLEX-CLIENT-REACH. `help` says "propose", never "run": this verb is
    # read-only and the wording is the only thing an operator reads before
    # deciding whether it is safe to try.
    sp = sub.add_parser(
        "reflex",
        help="show what the taught rule library PROPOSES for the live screen (read-only)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                    help="daemon run directory override")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    # WO-REFLEX-ARMED-RUN. `store_true` with no value form, and no sibling
    # `--yes`: the flag asks the question, it cannot answer it. The help says
    # "ask", never "run", because this word is what an operator reads before
    # deciding whether the command is safe to try.
    sp.add_argument("--arm", action="store_true",
                    help="after the proposal, ask y/N to launch it (never launches unprompted)")
    sp.set_defaults(func=cmd_reflex)

    # WO-RULE-WRITER-DRAFTS. The `rule` verb's handlers live in
    # `tw2002_aiclient/rules/cli.py`: they touch only the filesystem, so the
    # daemon's request/response plumbing would buy nothing, and this module is
    # already over the line cap (#218). Imported here rather than at module
    # scope so the CLI's import cost stays where the other verbs put it.
    from ..rules.cli import add_rule_parser

    add_rule_parser(sub)

    # WO-BUILD-SERVERS-PROBE-CLI-VERBS: catalog verbs live in catalog_cli
    # (daemon-free inventory/TCP probe) so this file stays under the line
    # cap the same way `rules.cli` does.
    from ..catalog_cli import add_catalog_parsers

    add_catalog_parsers(sub)

    # WO-BUILD-PLAYER-ROTATION-SELECTOR: read-only next_player surface.
    from ..players_cli import add_players_parsers

    add_players_parsers(sub)

    # WO-BUILD-WIRE-TW-MINE-CLI-VERB: ledger candidate mining (filesystem only).
    from ..mine_cli import add_mine_parsers

    add_mine_parsers(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
