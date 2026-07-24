"""``tw`` — the one-shot CLI. Talks to ``twd`` over its unix socket.

Every verb is a single connect -> send JSON -> read JSON line -> disconnect
round trip, so a Bash-driving agent never has to hold a socket open (see
canon's `architecture/session-engine.md`, "The Unix-Socket JSON Verb
Protocol"). Verb table starts empty (WO-P0-004) and grows one WO at a time;
``ensure``/``status`` land here under WO-P2-020 -- APPEND new verbs to
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

try:
    import tomllib
except ImportError:  # pragma: no cover -- pre-3.11 fallback, mirrors credentials.py
    import tomli as tomllib  # type: ignore

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
    """Resolve `profile_name`'s (host, port) out of `config/profiles.toml`,
    following a `server` catalog key into `config/servers.toml` when the
    profile doesn't set an explicit host/port -- the same resolution
    `credentials.list_profile_summaries()` performs for display, but that
    helper never surfaces a resolved *port* (display-only), so it's
    re-done here off the same on-disk sources (`credentials.PROFILES_PATH`,
    `credentials.list_servers()`) rather than duplicating the catalog read.
    """
    profiles_path = credentials.PROFILES_PATH
    if not profiles_path.exists():
        raise ProfileResolutionError(f"{profiles_path} does not exist")
    with open(profiles_path, "rb") as f:
        data = tomllib.load(f)
    section = data.get(profile_name)
    if not isinstance(section, dict):
        raise ProfileResolutionError(f"no [{profile_name}] section in {profiles_path}")

    host = section.get("host")
    port = section.get("port")
    server_key = section.get("server")
    if server_key and (host is None or port is None):
        catalog = {str(s["key"]): s for s in credentials.list_servers()}
        entry = catalog.get(str(server_key))
        if entry is None:
            raise ProfileResolutionError(
                f"[{profile_name}] server={server_key!r} not found in config/servers.toml"
            )
        if host is None:
            host = entry.get("host")
        if port is None:
            port = entry.get("port")

    if not host:
        raise ProfileResolutionError(
            f"[{profile_name}] has no resolvable host -- set host= or a valid server= catalog key"
        )
    if not port:
        raise ProfileResolutionError(
            f"[{profile_name}] has no resolvable port -- set port= or a valid server= catalog key"
        )
    return str(host), int(port)


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
        remaining = deadline - time.monotonic()
        if remaining > 0:
            send_request("read", {"timeout": remaining}, timeout=remaining + 5, run_dir=run_dir)

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
                     help="skip post-ensure Autopilot auto-start even when the profile enables it")
    sp.add_argument("--run-dir", default=None, metavar="PATH", dest="run_dir",
                     help="daemon run directory override (default: project-rooted run/)")
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_ensure)

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
