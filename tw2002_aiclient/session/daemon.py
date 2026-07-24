"""twd -- the session daemon (canon: `canon/architecture/session-engine.md`
"The Two-Process Split" / "Single-Connection Invariant").

Owns ONE telnet connection to the TWGS server and serves it over a
unix-domain JSON socket at `<run-dir>/twd.sock`. Refuses a second connect
via the pidfile at `<run-dir>/twd.pid` -- both project-rooted through
`env.py` regardless of the caller's CWD, never reimplemented here.

Ported from `archive/pre-rebirth-2026-07-23/code/twclient/daemon.py`
(WO-P2-020, Wave-3 + WO-P2-025 control-lock wire). Still cut vs archive:
`LedgerWriter`, `SkillRecorder`, `WatchHub`, `SessionGuardian`,
`LoopPlayer`, `FrameRecorder` (`ledger.py`, `guardian.py`, `watch.py`,
`loop_player.py`, `frame_recorder.py`, `autopilot.py`). Live verbs:
`ensure`/`status`/`screen`/`stop` plus lifetime `attach` (control-lock
hold). `subscribe` stays cut until `watch.py` lands. `protocol.dispatch()`
reads server-side collaborators via `getattr(server, ..., None)`.
"""

import argparse
import json
import os
import socketserver
import sys
import threading
import time

from . import env
from .control_lock import ControlLock, ControlModeConflict
from .protocol import dispatch
from .session import Session


class ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


class CommandHandler(socketserver.StreamRequestHandler):
    def handle(self):
        session = self.server.session
        while True:
            line = self.rfile.readline()
            if not line:
                return
            try:
                req = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond({"ok": False, "error": "invalid_json"})
                continue
            if not isinstance(req, dict):
                # Valid JSON but not a request object (e.g. a bare list
                # or number) -- still a malformed request, never a crash.
                self._respond({"ok": False, "error": "invalid_request"})
                continue
            verb = req.get("verb")
            if verb == "attach":
                # Lifetime connection: holds MODE_HUMAN until the socket
                # drops (see _handle_attach). Never returns to one-shot
                # request/response on this connection.
                self._handle_attach()
                return
            args = req.get("args") or {}
            try:
                result = dispatch(session, verb, args, self.server)
            except Exception as e:  # noqa: BLE001 -- a bad request must never kill the daemon
                result = {"ok": False, "error": f"internal_error:{e}"}
            self._respond(result)

    def _handle_attach(self):
        """Thin `tw attach` — take_human for the connection lifetime;
        each subsequent line is one raw keystroke frame `{"key": "..."}`
        forwarded via `session.send_raw(..., control_lock=..., sender=
        "human")`. Release on any exit so a crashed attach cannot wedge
        MODE_HUMAN. Ledger/record_attach_keystroke deferred (no ledger).
        """
        lock = self.server.control_lock
        session = self.server.session
        try:
            lock.take_human()
        except ControlModeConflict as e:
            self._respond({"ok": False, "error": str(e)})
            return
        try:
            self._respond({"ok": True, "attached": True})
            while True:
                line = self.rfile.readline()
                if not line:
                    return
                try:
                    req = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._respond({"ok": False, "error": "invalid_json"})
                    continue
                key = req.get("key")
                if not isinstance(key, str):
                    self._respond({"ok": False, "error": "missing_key"})
                    continue
                session.send_raw(
                    key.encode("latin-1", errors="ignore"),
                    control_lock=lock,
                    sender="human",
                )
                self._respond({"ok": True})
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            lock.release_human()

    def _respond(self, obj):
        self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))


def _attempt_graceful_quit(session):
    """Best-effort in-game QUIT before disconnecting. Never raises."""
    try:
        if session.classify() != "main_command":
            return
        session.send("Q")
        session.wait_settle(timeout=2.0)
        session.send("Y")
        session.wait_settle(timeout=2.0)
    except Exception:
        pass


def _shutdown(server, session):
    # Give the 'stop' response a moment to flush to the CLI client before
    # we tear the connection down.
    time.sleep(0.2)
    _attempt_graceful_quit(session)
    session.close()
    server.shutdown()


def _cleanup(run_dir):
    for name in (env.PID_NAME, env.SOCK_NAME):
        path = run_dir / name
        try:
            path.unlink()
        except OSError:
            pass


class _PidfileHeld(Exception):
    """Raised by `_claim_pidfile()` when a genuinely live process already
    holds the pidfile -- carries that pid so `main()` can report it."""

    def __init__(self, pid):
        super().__init__(f"pidfile held by pid {pid}")
        self.pid = pid


def _claim_pidfile(pidfile):
    """**Mack adversarial-review fix (HIGH, reproduced):** atomically
    claim `pidfile` via `O_CREAT | O_EXCL`, replacing the old
    check-`pidfile.exists()`-then-write shape. That check-then-write was a
    TOCTOU race: two concurrent cold-start spawns (e.g. two `ensure_raw()`
    callers racing to spawn the daemon) could BOTH pass the
    `pidfile.exists()` check before either had written it, both proceed to
    `session.start()`, and both end up holding a live telnet connection --
    one pid wins the pidfile's final write, the OTHER becomes an orphaned,
    invisible-to-`status` second connection. That's a direct violation of
    the single-connection invariant (`canon/architecture/session-engine.md`),
    not just a cosmetic race.

    `O_EXCL` makes the create+claim a single atomic kernel operation: only
    ONE process can ever win it for a given path. A `FileExistsError` means
    someone else got there first -- read the existing pid: genuinely ALIVE
    (`os.kill(pid, 0)` succeeds) -> raise `_PidfileHeld` for the caller to
    report and exit on; STALE (dead process, or an unreadable/corrupt
    leftover) -> unlink it and retry the atomic create exactly once (not
    an unbounded retry loop -- a second collision right after our own
    unlink means a sibling won the same race we're in, which is the
    ordinary "someone else is live" case, not a reason to spin)."""
    for _attempt in range(2):
        try:
            fd = os.open(str(pidfile), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                existing_pid = int(pidfile.read_text().strip())
                os.kill(existing_pid, 0)
            except (OSError, ValueError):
                # Stale pidfile (dead process, or unreadable/corrupt) --
                # step over it and retry the atomic create once.
                try:
                    pidfile.unlink()
                except OSError:
                    pass
                continue
            raise _PidfileHeld(existing_pid)
        else:
            with os.fdopen(fd, "w") as f:
                f.write(str(os.getpid()))
            return
    # Two collisions in a row: a sibling won the retry too. Report it as
    # held rather than looping -- refuse, never spin.
    try:
        existing_pid = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        existing_pid = None
    raise _PidfileHeld(existing_pid)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="twd")
    parser.add_argument("--host", default=None, help="defaults via TW2002_HOST / .env / profiles.toml -- see env.py")
    parser.add_argument("--port", type=int, default=None, help="defaults via TW2002_PORT / .env / profiles.toml -- see env.py")
    parser.add_argument("--name", default=None)
    args = parser.parse_args(argv)

    try:
        host, port = env.resolve_host_port(args.host, args.port)
    except env.EnvResolutionError as e:
        print(f"twd: {e}", file=sys.stderr)
        sys.exit(1)

    # Project-rooted run/ + pidfile + socket -- owned by env.py (Single-
    # Connection Invariant), never reimplemented here.
    run_dir = env.resolve_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)
    sock_path = env.socket_path(run_dir)
    pidfile = env.pid_path(run_dir)

    # Claim the pidfile FIRST, atomically -- see _claim_pidfile()'s own
    # docstring. This is the actual single-connection guard; everything
    # after this line assumes we -- and only we -- hold it.
    try:
        _claim_pidfile(pidfile)
    except _PidfileHeld as e:
        print(f"twd: already running (pid {e.pid}); refusing second connection", file=sys.stderr)
        sys.exit(1)

    if sock_path.exists():
        sock_path.unlink()

    # **Mack adversarial-review fix (MED, reproduced):** `session.start()`
    # used to run AFTER the pidfile was already written, uncaught -- a
    # dead-port/unreachable-host connect failure raised straight out of
    # `main()` as an unhandled traceback AND left a stale pidfile (holding
    # OUR now-dead pid) behind for the next spawn attempt to trip over.
    # Catch it, report cleanly, and RELEASE the pidfile we just claimed --
    # a daemon that never got a working connection must leave no trace.
    try:
        session = Session(host, port, args.name, str(env.LOG_DIR))
        session.start()
    except Exception as e:
        print(f"twd: failed to connect to {host}:{port}: {e}", file=sys.stderr)
        try:
            pidfile.unlink()
        except OSError:
            pass
        sys.exit(1)

    server = ThreadingUnixServer(str(sock_path), CommandHandler)
    server.session = session
    # WO-P2-025: mode + active-driver slot (replaces the earlier ensure-only
    # `threading.Lock` drive_lock). Eager so every request sees one lock;
    # protocol `_driving_dispatch` uses acquire_driver/release_driver.
    server.control_lock = ControlLock()
    server.request_stop = lambda: threading.Thread(target=_shutdown, args=(server, session), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        _cleanup(run_dir)


if __name__ == "__main__":
    main()
