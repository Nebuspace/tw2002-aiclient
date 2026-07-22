"""twd — the session daemon.

Owns ONE telnet connection to the TWGS server and serves it over a
unix-domain JSON socket at <run-dir>/twd.sock. Spawned detached by
`tw start` (DESIGN.md §3, §8); refuses a second connect via the pidfile.
"""

import argparse
import json
import os
import queue
import socketserver
import sys
import threading
import time

from .classify import classify
from .control_lock import ControlLock, ControlModeConflict
from .credentials import get_password, save_password
from .frame_recorder import FrameRecorder
from .guardian import SessionGuardian
from .ledger import LedgerWriter
from .loop_player import LoopPlayer
from .protocol import dispatch, record_attach_keystroke
from .session import Session
from .skills import SkillRecorder
from .watch import WatchHub

SOCK_NAME = "twd.sock"
PID_NAME = "twd.pid"


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
            verb = req.get("verb")
            if verb == "subscribe":
                # A subscribe connection's whole lifetime is the stream —
                # it never goes back to one-shot request/response.
                self._handle_subscribe()
                return
            if verb == "attach":
                # Same deal: a `tw attach` connection's whole lifetime IS
                # its human-control-lock hold. See _handle_attach().
                self._handle_attach()
                return
            args = req.get("args") or {}
            try:
                result = dispatch(session, verb, args, self.server)
            except Exception as e:  # noqa: BLE001 — a bad request must never kill the daemon
                result = {"ok": False, "error": f"internal_error:{e}"}
            self._respond(result)

    def _handle_subscribe(self):
        hub = self.server.watch_hub
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
        """A `tw attach` session's whole lifetime is this connection —
        like _handle_subscribe(), it never returns to one-shot
        request/response. Takes the control-lock for as long as the
        connection stays open; every subsequent line is one raw
        keystroke frame {"key": "..."} forwarded straight to the game via
        session.send_raw(), acked with a bare {"ok": true} (the live
        screen itself streams over a SEPARATE `subscribe` connection —
        `tw attach` opens both, mirroring spectate_app.SpectateClient's
        status/stream split — see interactive_app.py). Releasing the
        lock on ANY exit path (clean detach, Ctrl-C, or a dropped socket)
        is the whole safety property: a crashed attach session can never
        wedge the daemon in human-controlled state.

        `key` travels as a JSON string holding the raw bytes' Latin-1
        code points (0-255) — every byte an interactive keystroke can
        produce (printable ASCII, control chars, ANSI cursor escapes)
        round-trips exactly through JSON that way, decoded back to bytes
        with .encode("latin-1") on this end.

        WO-CLEANPREEMPT: `take_human()` above always succeeds instantly
        even while an ai_pilot dispatch is actively mid-flight (fencing
        it instead of refusing -- see control_lock.py) -- so every
        keystroke send below passes `self.server.control_lock` through
        to `session.send_raw()`, which holds the byte off the wire until
        any such fenced dispatch actually releases (a clean cutover onto
        the one wire). Each keystroke is also now routed into the same
        Trace-Ledger every do/send/haggle dispatch writes to
        (`record_attach_keystroke`, `actor="human"`) -- the branch
        `protocol._current_actor()`'s own docstring anticipated since
        TW-05.

        WO-CLEANPREEMPT (secret sub-diff, cipher's proven leak): every
        keystroke was previously logged UNREDACTED to the transcript --
        `session.send_raw()` now decides `secret` itself (from the
        CURRENT screen, right before the byte hits the wire) and gates
        `connection.send_bytes()`'s own log line on it; `session.
        last_sent_secret` carries that SAME decision back here so
        `record_attach_keystroke`'s ledger row agrees with it -- one
        decision, two sinks, never a second independent (and possibly
        stale) derivation.
        """
        lock = self.server.control_lock
        session = self.server.session
        try:
            lock.take_human()
        except ControlModeConflict as e:
            self._respond({"ok": False, "error": str(e)})
            return
        # Everything from here on, including the very first ack, must be
        # inside the try/finally -- a dead client (e.g. vanished the
        # instant it connected) can make even that first write raise,
        # and a lock release skipped by an early uncaught exception here
        # would wedge the daemon in human-controlled state forever.
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
                pre_text = session.render_text(session.render())
                session.send_raw(key.encode("latin-1", errors="ignore"), control_lock=lock)
                # WO-CLEANPREEMPT (secret sub-diff): `session.last_sent_secret`
                # is send_raw()'s OWN send-time decision (the CURRENT
                # screen, evaluated post-fence-wait, right before the
                # byte hit the wire) -- read back here and threaded
                # through so the ledger row agrees with the transcript
                # log's own redaction, never re-derived a second,
                # potentially-stale way from `pre_text` (which was
                # captured BEFORE the fence-wait even started).
                record_attach_keystroke(
                    self.server, session, pre_text, session.last_sent, session.last_sent_secret
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
        text = session.render_text()
        if classify(text) != "main_command":
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
    server.guardian.stop()
    server.loop_player.stop()  # signal only -- never blocks on the thread joining
    _attempt_graceful_quit(session)
    server.watch_hub.stop()
    session.close()
    server.shutdown()


def _cleanup(run_dir):
    for name in (PID_NAME, SOCK_NAME):
        path = os.path.join(run_dir, name)
        try:
            os.remove(path)
        except OSError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="twd")
    parser.add_argument("--host", default=None, help="defaults via TW2002_HOST / .env / profiles.toml -- see twclient/env.py")
    parser.add_argument("--port", type=int, default=None, help="defaults via TW2002_PORT / .env / profiles.toml -- see twclient/env.py")
    parser.add_argument("--name", default=None)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--log-dir", required=True)
    args = parser.parse_args(argv)

    from .env import EnvResolutionError, resolve_host_port
    try:
        host, port = resolve_host_port(args.host, args.port)
    except EnvResolutionError as e:
        print(f"twd: {e}", file=sys.stderr)
        sys.exit(1)

    run_dir = args.run_dir
    os.makedirs(run_dir, exist_ok=True)
    sock_path = os.path.join(run_dir, SOCK_NAME)
    pid_path = os.path.join(run_dir, PID_NAME)

    if os.path.exists(pid_path):
        try:
            existing_pid = int(open(pid_path).read().strip())
            os.kill(existing_pid, 0)
            print(f"twd: already running (pid {existing_pid}); refusing second connection", file=sys.stderr)
            sys.exit(1)
        except (OSError, ValueError):
            pass  # stale pidfile — proceed

    if os.path.exists(sock_path):
        os.remove(sock_path)

    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

    session = Session(host, port, args.name, args.log_dir)
    session.start()

    watch_hub = WatchHub(session)
    watch_hub.start()

    # D9 reconnect+login-replay / D10 idle-keepalive (SessionGuardian) --
    # starts inert (session.auto_login_profile is None until a successful
    # `ensure` call records one) and stopped cleanly on daemon shutdown.
    guardian = SessionGuardian(session, get_password=get_password, save_password=save_password)
    guardian.start()

    server = ThreadingUnixServer(sock_path, CommandHandler)
    server.session = session
    server.watch_hub = watch_hub
    server.guardian = guardian
    # Interactive `tw attach` / control-lock (see control_lock.py,
    # CommandHandler._handle_attach, protocol.py's do/send guard):
    # always-on core infrastructure, not an optional add-on like
    # ledger/skill_recorder below, so it's set unconditionally.
    server.control_lock = ControlLock()
    # v2.1 item 11: the Trace-Ledger (C1) is always-on for every do/send
    # this daemon dispatches; the SkillRecorder (C3) only accumulates
    # steps while a `tw record` capture is open (server.skill_recorder.
    # recording). Both read via protocol.py's dispatch(), never edited by
    # a subagent that isn't this build (session.py/login.py/guardian.py
    # stay untouched).
    server.ledger = LedgerWriter()
    server.skill_recorder = SkillRecorder()
    # WO-FRAMES-0: full-grid settle frames for post-mortem (Option?/qty).
    # Attached on the session so protocol.build_response can append without
    # threading server through every call site.
    session.frame_recorder = FrameRecorder(session.logger.session_id)
    # Trainer Control Panel (TUI-POLISH-PLAN.md) -- the AUTO-LOOP
    # background driver (loop_player.py); always-on infrastructure like
    # control_lock above, not gated behind any capture-open flag.
    # TW-04: reuses this daemon's own Trace-Ledger + TranscriptLogger
    # session id (set in Session.__init__, always present on a real
    # session by this point) so every AUTO-LOOP send gets the same
    # actor="trainer" ledger row a `tw replay`/`tw play` dispatch does.
    server.loop_player = LoopPlayer(
        session, server.control_lock, watch_hub, ledger=server.ledger, session_id=session.logger.session_id
    )
    # §22/§23 Phase 1 autonomous goal-orchestrator (autopilot.py) -- WO-P1-d
    # wiring: `server.autopilot_engine` is lazily constructed/reused by
    # protocol.py's `autopilot_preview`/`autopilot_start` dispatches (see
    # `_get_or_build_autopilot_engine`), and `server.autopilot_loop` is set
    # only once `autopilot_start` actually arms a background `AutopilotLoop`
    # (mirrors `server.loop_player` above, but this one starts absent -- an
    # AUTO_LOOP run only ever exists after an explicit `tw autopilot start`,
    # never unconditionally like the always-on Trainer Control Panel driver).
    # Both stay `None` until first used; protocol.py's "status" handler
    # already reads autopilot_engine null-safe (same getattr(..., None)
    # convention as watch_hub/control_lock/loop_player).
    server.autopilot_engine = None
    server.autopilot_loop = None
    server.request_stop = lambda: threading.Thread(target=_shutdown, args=(server, session), daemon=True).start()

    try:
        server.serve_forever()
    finally:
        _cleanup(run_dir)


if __name__ == "__main__":
    main()
