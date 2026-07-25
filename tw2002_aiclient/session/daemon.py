"""twd -- the session daemon (canon: `canon/architecture/session-engine.md`
"The Two-Process Split" / "Single-Connection Invariant").

Owns ONE telnet connection to the TWGS server and serves it over a
unix-domain JSON socket at `<run-dir>/twd.sock`. Refuses a second connect
via the pidfile at `<run-dir>/twd.pid` -- both project-rooted through
`env.py` regardless of the caller's CWD, never reimplemented here. A third,
daemon-private run-dir artifact is `<run-dir>/twd.errors.log` (mode 0600):
the local sink for the dispatch-catch traceback whose text no longer goes
on the wire (WO-AUDIT-F5-TYPE-NAME). It is not part of the run-dir contract
`env.py` publishes -- no other module reads it -- so its name lives here.

Ported from `archive/pre-rebirth-2026-07-23/code/twclient/daemon.py`
(WO-P2-020, Wave-3 + WO-P2-025 control-lock wire + WO-P2-027 SessionGuardian
D9 reconnect/replay). Still cut vs archive: `LedgerWriter`, `SkillRecorder`,
`LoopPlayer`, `FrameRecorder` (`ledger.py`, `loop_player.py`,
`frame_recorder.py`, `autopilot.py`). Guardian D10 keepalive stays
stubbed until WO-P2-028. Live verbs: `ensure`/`status`/`screen`/`stop`
plus lifetime `attach` (control-lock hold) and `subscribe` (WatchHub
settle-edge stream — WO-P2-WATCHHUB-PORT). `protocol.dispatch()` reads
server-side collaborators via `getattr(server, ..., None)`.
"""

import argparse
import json
import os
import queue
import socketserver
import sys
import threading
import time
import traceback

from . import env
from .control_lock import ControlLock, ControlModeConflict
from .credentials import get_password
from .guardian import SessionGuardian
from .protocol import _save_password, dispatch
from .session import Session
from .watch import WatchHub


ERRLOG_NAME = "twd.errors.log"


def _open_error_log(run_dir):
    """Open the daemon's owner-only local diagnostic sink.

    This exists so that `CommandHandler.handle()`'s unbounded catch can send
    a bare type name over the wire without the daemon going BLIND: before
    WO-AUDIT-F5-TYPE-NAME the wire string was the only record anywhere that
    a dispatch had raised at all -- nothing was logged, so "just say less on
    the wire" would have destroyed the only diagnostic instead of relocating
    it.

    Mode `0600` at `os.open()` and re-asserted after, exactly like
    `logging_util.TranscriptLogger` (and `protocol._save_password`): a log
    that can carry caller-supplied bytes never gets the umask default.
    Deliberately NOT stderr -- `cli.py`'s daemon spawn appends the daemon's
    stdout+stderr to `run/twd.stderr.log`, which it opens at plain umask
    default (observed 0644 on a live run dir), and routing arbitrary
    exception text into a world-readable file is the opposite of the point.
    `main()`'s startup `print(..., file=sys.stderr)` calls stay as they are:
    their content is bounded (a resolver error, a host/port connect failure),
    a dispatch traceback's is not.

    Not unlinked by `_cleanup()`: a diagnostic that disappears when the
    daemon exits is not a diagnostic.
    """
    path = run_dir / ERRLOG_NAME
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    fh = os.fdopen(fd, "a", buffering=1, encoding="utf-8", errors="replace")
    os.chmod(str(path), 0o600)  # re-assert even if the file pre-existed looser
    return fh


def _log_dispatch_error(server, verb, exc):
    """Record a dispatch exception locally, in full, so type-name-only on
    the wire is quieter rather than blinder.

    WHAT GOES IN: the exception's own text and the frame chain.
    `traceback.format_exc()` does not capture frame locals, so this is
    exactly what the wire used to carry plus the file/line trail -- the
    change is not "less information exists", it is "no client can ask for
    it". `verb` is included because it is the routing key: reaching here
    means `dispatch()` already MATCHED one of its own verb literals (an
    unrecognized verb returns `unknown_verb` without raising), so this
    string is the daemon's, not the caller's.

    WHAT STAYS OUT: the request's `args`. That dict is structurally where a
    secret rides -- `do`/`send` take `{"input": ..., "secret": true}` -- and
    keeping password bytes out of a log is precisely what the redaction sink
    (`canon/doctrine/secrets-and-credentials.md`) exists for. A traceback is
    not a redaction sink and must not be used as one.

    This is a REDUCTION in exposure, not a guarantee: `str(exc)` can still
    echo caller-supplied bytes -- that is how `int()`'s ValueError became a
    wire leak in the first place -- so this file inherits the exposure the
    wire is losing. It is local, owner-only, and operator-owned, which is a
    different risk class, not an absent one. Whether any real secret-bearing
    path can land a secret in an exception message is UNVERIFIED; it is not
    claimed here in either direction.
    """
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    text = f"[{stamp}] dispatch verb={verb!r} raised {type(exc).__name__}\n{traceback.format_exc()}"
    fh = getattr(server, "error_log", None)
    if fh is None:
        # No run-dir sink (a bare unit-test harness builds the server by
        # hand). Still never silent -- the harness's captured stderr is the
        # right home there, and the 0644 concern above is a run-dir concern.
        sys.stderr.write(text)
        return
    try:
        fh.write(text)
    except (OSError, ValueError):
        pass  # a broken diagnostic sink must never take the daemon down


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
            if verb == "subscribe":
                # Lifetime connection: settle-edge stream until the socket
                # drops (see _handle_subscribe). Read-only — never takes
                # control_lock / never sends game input.
                self._handle_subscribe()
                return
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
                # WO-AUDIT-F5-TYPE-NAME: the TYPE NAME goes on the wire, the
                # traceback goes to the local log. This is the widest catch
                # in the package, so nothing here knows the message's
                # provenance -- and two leaks were reproduced straight
                # through it over a real AF_UNIX socket:
                #   ensure  + an unreadable config -> `internal_error:
                #             [Errno 21] Is a directory: '<absolute path>'`
                #             -- server-side filesystem layout the client
                #             never supplied,
                #   history + a non-integer `n` -> `int()`'s ValueError,
                #             which reprs its own argument, handing the
                #             caller's bytes back out of the same `args`
                #             dict a `--secret` payload rides in.
                #
                # This does NOT generalize to "never emit str(e)". The rule
                # is about the CATCH, not the string: full text when the
                # catch is narrow enough to bound the provenance, type name
                # when it is unbounded. `guardian.py` shows both halves in
                # one file -- its `except (OSError, LoginError)` keeps
                # `str(e)` on purpose, while its `except Exception` records
                # `guardian_tick_error:{type(e).__name__}`. Sweeping the
                # narrow sites onto this line would be a regression dressed
                # up as consistency.
                #
                # The type name also closes the worst shape structurally,
                # not just the two observed ones. `str(e)` never rendered
                # `JSONDecodeError.doc` / `UnicodeDecodeError.object`, but
                # those attributes hold the ENTIRE document that failed to
                # parse, and `ensure` -> `_dispatch_ensure` -> `run_login`
                # -> `credentials.get_password` -> `json.load(open(
                # SECRETS_PATH))` is a live, uncaught path to raising one of
                # them off the secrets file. A type name cannot carry a
                # document, whatever a future edit does to the format
                # string. Whether a real secret has ever reached this line
                # is UNVERIFIED -- this narrows the exposure; it does not
                # earn the word "safe".
                _log_dispatch_error(self.server, verb, e)
                result = {"ok": False, "error": f"internal_error:{type(e).__name__}"}
            self._respond(result)

    def _handle_subscribe(self):
        hub = getattr(self.server, "watch_hub", None)
        if hub is None:
            self._respond({"ok": False, "error": "watch_hub_unavailable"})
            return
        q = hub.subscribe(queue.Queue)
        try:
            while True:
                event = q.get()
                self._respond(event)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            hub.unsubscribe(q)

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
                # WO-AUDIT-KEYDROP-HONESTY: never answer `{"ok": true}` for a
                # keystroke that did not reach the wire. This was
                # `key.encode("latin-1", errors="ignore")`, which turns any
                # character above U+00FF into `b""`; `send_raw(b"")` then
                # `sendall(b"")`s a no-op and we still claimed delivery.
                # Three surfaces disagreed about that one non-event: the
                # transcript log stayed silent, `last_sent` (served to every
                # spectator) reported an empty send, and the LOGS tail gained
                # a phantom `human> ` row.
                #
                # Both refusals below `continue`, exactly like `invalid_json`
                # and `missing_key` above -- a key we cannot represent is a
                # bad frame, never a reason to drop the operator's attach
                # connection or release their MODE_HUMAN lock out from under
                # them.
                #
                # These two errors are the daemon's contract for ANY client;
                # the shipped client does not reach them, but only ONE of its
                # two paths gets there by refusing (this comment used to say
                # "refused client-side" flat, which covered the interactive
                # path only):
                #   interactive `tw attach` -- a genuine refusal.
                #     `cli.py::cmd_attach` catches `UnicodeEncodeError` per
                #     keystroke, reports it inline, sends nothing, and keeps
                #     the session.
                #   scripted `tw attach --keys` -- not a refusal at all.
                #     Verified by execution against this worktree's cli.py
                #     (origin ae95271): that path re-encodes the value
                #     `utf-8 -> unicode_escape -> latin-1(errors="ignore")`,
                #     which leaves every byte latin-1-representable by
                #     construction, so the frame it builds can never carry an
                #     unencodable key; a value with nothing left to send is
                #     skipped before the wire rather than answered here.
                # A `cli.py` lane was in flight when this was written and may
                # have changed the `--keys` half -- re-verify that clause,
                # not this daemon contract, which holds either way.
                try:
                    data = key.encode("latin-1")
                except UnicodeEncodeError:
                    # The wire is healthy; THIS character has no 8-bit form.
                    self._respond({"ok": False, "error": "unencodable_key"})
                    continue
                if not data:
                    # Present, well-formed, and zero bytes long -- distinct
                    # from `missing_key` (absent / not a string) because the
                    # field IS there. Nothing reaches the game either way, so
                    # `{"ok": true}` would be the same lie in a narrower
                    # costume, phantom `human> ` row and all.
                    self._respond({"ok": False, "error": "empty_key"})
                    continue
                session.send_raw(data, control_lock=lock, sender="human")
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
    guardian = getattr(server, "guardian", None)
    if guardian is not None:
        guardian.stop()
    watch_hub = getattr(server, "watch_hub", None)
    if watch_hub is not None:
        watch_hub.stop()
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

    # D9 reconnect+login-replay (SessionGuardian) -- starts inert
    # (session.auto_login_profile is None until a successful `ensure`
    # records one) and stopped cleanly on daemon shutdown. D10 keepalive
    # is stubbed inside guardian until WO-P2-028.
    guardian = SessionGuardian(
        session,
        get_password=get_password,
        save_password=_save_password,
    )
    guardian.start()

    # WO-P2-WATCHHUB-PORT: settle-edge push-stream for subscribe / future
    # tw watch + spectate. Read-only hub — never drives the game.
    watch_hub = WatchHub(session)
    watch_hub.start()

    # WO-AUDIT-F5-TYPE-NAME: opened only once we are certainly the live
    # daemon (pidfile claimed, telnet connected), so a refused second spawn
    # or a failed connect still "leaves no trace" the way the two exits
    # above already do. Owner-only; see `_open_error_log`.
    error_log = _open_error_log(run_dir)

    server = ThreadingUnixServer(str(sock_path), CommandHandler)
    server.session = session
    server.guardian = guardian
    server.watch_hub = watch_hub
    server.error_log = error_log
    # WO-P2-025: mode + active-driver slot (replaces the earlier ensure-only
    # `threading.Lock` drive_lock). Eager so every request sees one lock;
    # protocol `_driving_dispatch` uses acquire_driver/release_driver.
    server.control_lock = ControlLock()
    server.request_stop = lambda: threading.Thread(target=_shutdown, args=(server, session), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        _cleanup(run_dir)
        error_log.close()


if __name__ == "__main__":
    main()
