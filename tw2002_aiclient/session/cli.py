"""``tw`` — the backend/ops CLI. Talks to ``twd`` over its unix socket.

Most verbs are a single connect -> send JSON -> read JSON line -> disconnect
round trip. ``tw watch`` is the exception: a lifetime ``subscribe`` stream
(NDJSON settle-edge events) until ``--frames N`` or Ctrl-C (see canon
`architecture/session-engine.md`). Verb table grows one WO at a time;
``ensure``/``status`` land under WO-P2-020 -- APPEND new verbs to
``build_parser()``, never rewrite an already-landed one.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import argparse

from . import credentials, env


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
    pid_path = env.pid_path(run_dir)
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
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
    resp = send_request("status", {}, run_dir=run_dir)
    resp["daemon_running"] = True
    resp["run_dir"] = str(run_dir)
    print_response(resp, args)
    return 0 if resp.get("ok") else 1


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

        # Let the fresh connection produce its first settled screen
        # before driving it -- mirrors `tw start`'s post-spawn read.
        # Cap the settle window so a slow/idle first screen cannot burn
        # the whole ensure budget (WO-P2-OPS-VERB-B: `read` is live now;
        # previously unknown_verb returned instantly and hid this hazard).
        remaining = deadline - time.monotonic()
        settle_budget = min(remaining, 5.0)
        if settle_budget > 0:
            send_request(
                "read",
                {"timeout": settle_budget},
                timeout=settle_budget + 5,
                run_dir=run_dir,
            )

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


def cmd_watch(args):
    """WO-P2-OPS-VERB-E2: tail the settle-edge push-stream (read-only).

    Opens a lifetime ``subscribe`` connection — never sends game input.
    ``--frames N`` exits after N events (transcript-friendly); otherwise
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
    you-are-here). Never sends. Localizes the live screen when a daemon
    is up; otherwise prints store-only with ``here off-map``."""
    from tw2002_aiclient.menu import knowledge as menu_knowledge
    from tw2002_aiclient.menu.map_view import (
        format_menu_map_report,
        menu_map_summary_from_store,
    )
    from tw2002_aiclient.menu.nav import localize

    path = args.path
    if not path and getattr(args, "world_id", None):
        path = str(menu_knowledge.knowledge_path_for_world(args.world_id))
    if not path:
        print("ERROR: need --path or --world-id")
        return 1

    run_dir = _resolve_run_dir(getattr(args, "run_dir", None))
    current_sig = None
    if daemon_alive(run_dir):
        resp = send_request("screen", {}, run_dir=run_dir)
        if resp.get("ok"):
            screen_text = "\n".join(resp.get("screen") or [])
            try:
                node = localize(screen_text, path) if screen_text.strip() else None
            except (OSError, ValueError, TypeError, KeyError):
                node = None
            if node:
                current_sig = node.get("signature")

    try:
        summary = menu_map_summary_from_store(path, current_sig=current_sig)
    except (OSError, ValueError, TypeError, KeyError, menu_knowledge.GameKnowledgeError) as e:
        print(f"ERROR: {e}")
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "path": path, **summary}))
        return 0
    for line in format_menu_map_report(summary):
        print(line)
    return 0


def cmd_attach(args):
    """WO-P2-OPS-VERB-F1: take control_lock and forward keystrokes (thin).

    No curses screen paint yet (F2 spectate). Interactive mode needs a TTY
    (cbreak until Ctrl-]). ``--keys`` sends latin-1 bytes then detaches —
    for FakeDaemon / scripted proof without a TTY.
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
            # Scripted: interpret escapes lightly — \\r \\n \\xNN and raw chars.
            data = keys.encode("utf-8").decode("unicode_escape").encode("latin-1", errors="ignore")
            if data:
                conn.send_key(data)
            return 0

        import termios
        import tty

        print("ATTACHED — Ctrl-] detach (thin attach: no live screen paint yet; use tw watch)", flush=True)
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                ch = sys.stdin.read(1)
                if not ch:
                    break
                code = ord(ch)
                if code == DETACH_KEY:
                    break
                if ch in ("\n", "\r"):
                    conn.send_key(b"\r\n")
                else:
                    conn.send_key(ch.encode("latin-1", errors="ignore"))
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
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
                     help="daemon run directory override (default: project-rooted run/)")
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
                     help="daemon run directory override (default: project-rooted run/)")
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
                     help="daemon run directory override (default: project-rooted run/)")
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
                     help="password entry — never persisted to the transcript log")
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
                     help="password entry — never persisted to the transcript log")
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
                     help="screen only — omit prompt/class/settled footer")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser(
        "attach",
        help="take the keyboard (control-lock); thin attach — no curses paint yet",
    )
    sp.add_argument(
        "--keys",
        default=None,
        metavar="BYTES",
        help="scripted keystroke(s) then detach (unicode-escape; no TTY required)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.set_defaults(func=cmd_attach)

    sp = sub.add_parser(
        "menumap",
        help=(
            "read-only menu-map inspector: coverage, dead-ends, orphans, "
            "and you-are-here ★ / off-map — never sends"
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
        help="world_id slug under state/world/ (joins …/game_knowledge.json)",
    )
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_menumap)

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
