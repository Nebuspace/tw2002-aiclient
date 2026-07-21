"""Shared test infrastructure for the interactive-attach / control-lock
tests (test_attach_protocol.py, test_interactive_app.py).

`fake_daemon` spins up a REAL `twclient.daemon.ThreadingUnixServer` +
`CommandHandler` (production code, unmodified) on a temp unix socket,
wired to a `FakeAttachSession` instead of a real telnet Session. This
proves the daemon's control-lock wiring over an actual socket connection
without ever touching the network or the live game -- the whole point
being that a test exercising `tw attach`'s real keystroke-forwarding path
must NOT be able to land on the live run/twd.sock (a second attach
against the real daemon mid-session could inject real keystrokes into
the actual live game).
"""

import functools
import json
import os
import pty
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from twclient import env as _env
from twclient.control_lock import ControlLock
from twclient.daemon import CommandHandler, ThreadingUnixServer
from twclient.loop_player import LoopPlayer
from twclient.session import Session
from twclient.watch import WatchHub


def resolve_fake_host_port(fake_host="twgs.test.example", fake_port=23):
    """Resolve a fake "connect target" host/port through the REAL
    env.py resolution code (the same code `tw start`/`twd` use), with
    the fake value injected via TW2002_HOST/TW2002_PORT (temporarily
    set, then restored) -- rather than a hand-typed literal sitting in
    test source. Any fixture that needs a stand-in config host/port
    should source it from here (or reuse FAKE_HOST/FAKE_PORT below)
    instead of typing its own string, so a real hostname has no natural
    home to land in as a copy-pasted default. (WO-GITINIT-SCRUB
    amendment 2, 2026-07-19 -- fixture SCREEN TEXT, i.e. captured game
    banners, is exempt from this and keeps a plain literal.)"""
    prior_host = os.environ.get(_env.HOST_VAR)
    prior_port = os.environ.get(_env.PORT_VAR)
    os.environ[_env.HOST_VAR] = fake_host
    os.environ[_env.PORT_VAR] = str(fake_port)
    try:
        return _env.resolve_host_port(
            dotenv_path=Path("/nonexistent-wo-gitinit-scrub.env"),
            profiles_path=Path("/nonexistent-wo-gitinit-scrub.toml"),
        )
    finally:
        if prior_host is None:
            os.environ.pop(_env.HOST_VAR, None)
        else:
            os.environ[_env.HOST_VAR] = prior_host
        if prior_port is None:
            os.environ.pop(_env.PORT_VAR, None)
        else:
            os.environ[_env.PORT_VAR] = prior_port


FAKE_HOST, FAKE_PORT = resolve_fake_host_port()


class _FakeConn:
    """Just enough of TelnetConnection's surface for protocol.py's
    "status" verb (`session.conn.connected`)."""

    def __init__(self):
        self.connected = True


class FakeAttachSession:
    """Enough surface for protocol.dispatch()'s do/send/status/screen
    verbs AND daemon.py's raw keystroke forwarding -- no network. Mirrors
    tests/test_watch.py's FakeSession + tests/test_login.py's
    FakeLoginSession conventions.

    TW-02: `send()`/`send_raw()`'s rx_count/last_rx bump is DEFERRED to
    the next `sleep()` call rather than applied synchronously -- matching
    the async-response convention `test_settle.py`'s `StagedSession` (and
    this codebase's other fakes, post-TW-02) already use. A synchronous
    same-call bump is already reflected in the `start_rx_count`
    `settle.wait_for_settle` captures at its OWN call start, so it would
    never observe a NEW arrival and would always resolve via "timeout" --
    load-bearing now that `skills.replay_skill` (driven here via
    `LoopPlayer`, see test_protocol_trainer_panel.py) routes its send
    through `settle.send_and_confirm`'s idle-based confirm path.

    `real_time_scale` (default 0.0, no real cost -- unchanged behavior
    for every test that doesn't set it) lets a LoopPlayer-driven test
    reintroduce controllable REAL wall-clock pacing per cycle: previously
    those tests monkeypatched `session.wait_settle` directly
    (`time.sleep(0.05)` per settle call) to keep a background AUTO-LOOP
    thread running slowly enough for the test's own real-time polling to
    observe/interrupt mid-run state -- but replay_skill no longer calls
    `session.wait_settle()` at all (TW-02), so that monkeypatch is now
    inert. Setting `_real_time_scale` scales every `sleep(seconds)` call
    by a REAL `time.sleep(seconds * scale)`, so a full confirm (roughly
    debounce_ms + stability_pause_s of fake-clock time) costs about
    `scale * 0.5` real seconds -- `0.1` reproduces the original ~50ms
    per cycle.

    `observe_credits`/`credits_snapshot` (WO-FA-SAFE) are the REAL
    `Session` methods (assigned directly off the class, not reimplemented
    -- same convention as tests/test_credits_supervision.py's/
    test_loop_player.py's/test_autopilot.py's own fakes), so a test using
    this session through the real dispatch/LoopPlayer/AutopilotEngine
    paths exercises the same hasattr-guarded calls those call sites make
    against a real `Session`, rather than silently falling through the
    hasattr guard to a fail-closed `None`/`None` this fixture predated.
    `self.lock` is a plain `threading.Lock`, the same shape `Session.lock`
    is -- both methods acquire it internally."""

    observe_credits = Session.observe_credits
    credits_snapshot = Session.credits_snapshot

    def __init__(self, initial_screen="Command [TL=00:00:00]:[1234] (?=Help)? :", real_time_scale=0.0):
        self._screen = initial_screen
        self.conn = _FakeConn()
        self.host = "fake-host"
        self.port = 0
        self.name = None
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self.history = []
        self.sent = []  # [(text, enter, secret), ...] via send()
        self.raw_sent = []  # [bytes, ...] via send_raw()
        # TX channel + attach caret (mirrors the real Session's fields --
        # see session.py) -- exercised by tests/test_protocol_trainer_panel.py.
        self.last_sent = None
        self.last_sent_ts = None
        # WO-CLEANPREEMPT (secret sub-diff): mirrors the real Session's
        # own `last_sent_secret` -- daemon.py's real _handle_attach reads
        # it back after send_raw() unconditionally, so this fake needs
        # the attribute even though no test here exercises real secret
        # classification (this fake's screen is static/non-realistic;
        # the actual redaction logic is proven against the real Session
        # in tests/test_session.py and tests/test_attach_redaction.py).
        self.last_sent_secret = False
        self._cursor = {"x": 0, "y": 0}
        self._pending_advance = False
        self._real_time_scale = real_time_scale
        self.lock = threading.Lock()
        self.last_credits = None
        self.last_credits_ts = None

    def render(self):
        return self._screen.split("\n")

    def render_with_color(self):
        return self.render(), []

    def render_raw(self):
        return self.render()

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())

    def cursor_pos(self):
        return dict(self._cursor)

    def clock(self):
        return self.t

    def sleep(self, seconds):
        if self._real_time_scale:
            time.sleep(seconds * self._real_time_scale)
        self.t += seconds
        if self._pending_advance:
            self._pending_advance = False
            self.rx_count += 1
            self.last_rx = self.t

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return "idle", 0.0

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self.last_sent = "<redacted>" if secret else text
        self.last_sent_ts = self.t
        self._pending_advance = True

    def send_raw(self, data: bytes, control_lock=None):
        # `control_lock` mirrors the real Session.send_raw()'s
        # WO-CLEANPREEMPT signature (daemon.py's real _handle_attach
        # always passes it) -- accepted here so the real
        # CommandHandler._handle_attach code path works unmodified
        # against this fake, honoring the same bounded fence-wait a real
        # Session would (a no-op in every existing fake_daemon test,
        # since none of them arrange a fenced driver first). Deliberately
        # REAL wall-clock (time.monotonic()/time.sleep()), not this
        # fake's own simulated `self.t` -- this wait is cross-thread
        # synchronization against a REAL ControlLock shared with the
        # daemon's other real threads, unrelated to the settle-detection
        # fake-clock semantics `sleep()`/`self.t` model elsewhere in this
        # fixture.
        if control_lock is not None:
            deadline = time.monotonic() + 10.0
            while control_lock.is_driver_fenced() and time.monotonic() < deadline:
                time.sleep(0.02)
        self.raw_sent.append(data)
        self.last_sent = data.decode("latin-1", errors="replace")
        self.last_sent_ts = self.t
        self._pending_advance = True

    def record_history(self, verb, args, prompt, classification, settled_reason):
        self.history.append((verb, args, prompt, classification, settled_reason))


class _FakeDaemon:
    """Mirrors daemon.py's main() wiring (real ThreadingUnixServer +
    CommandHandler + WatchHub, production code unmodified) against a
    FakeAttachSession -- a `tw attach` client also opens a `subscribe`
    connection for its output side (interactive_app.SpectateClient), so
    a WatchHub is real infrastructure here, not optional test scaffolding
    (ledger/skill_recorder stay absent -- protocol.py's getattr(...,
    None) convention already covers that)."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self.session = FakeAttachSession()
        self.control_lock = ControlLock()
        self.watch_hub = WatchHub(self.session)
        self.loop_player = LoopPlayer(self.session, self.control_lock, self.watch_hub)
        self.server = ThreadingUnixServer(self.sock_path, CommandHandler)
        self.server.session = self.session
        self.server.control_lock = self.control_lock
        self.server.watch_hub = self.watch_hub
        self.server.loop_player = self.loop_player
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.watch_hub.start()
        self._thread.start()

    def stop(self):
        self.loop_player.stop()  # signal only -- never blocks on the thread joining
        self.watch_hub.stop()
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def fake_daemon():
    """A fresh isolated fake daemon per test, on its own temp socket --
    never run/twd.sock, never the live game. AF_UNIX socket paths are
    capped at ~104 bytes on macOS/BSD, well under what pytest's own
    (deeply nested) tmp_path produces for a long test name -- a short
    mkdtemp() under /tmp is used instead, purely for the socket."""
    sock_dir = tempfile.mkdtemp(prefix="twd-test-")
    try:
        daemon = _FakeDaemon(f"{sock_dir}/s.sock")
        daemon.start()
        try:
            yield daemon
        finally:
            daemon.stop()
    finally:
        shutil.rmtree(sock_dir, ignore_errors=True)


def send_request(sock_path, verb, args=None, timeout=5.0):
    """One-shot request/response over the fake daemon's socket -- mirrors
    cli.py's send_request() exactly, kept local here to avoid pulling
    cli.py's project-rooted RUN_DIR/SOCK_PATH constants into tests."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(str(sock_path))
    payload = json.dumps({"verb": verb, "args": args or {}}) + "\n"
    s.sendall(payload.encode("utf-8"))
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    s.close()
    return json.loads(buf.decode("utf-8"))


# A no-op curses.wrapper() round-trip (initscr -> cbreak -> keypad ->
# nocbreak -> endwin) -- the exact minimum every real entry point these
# pty tests drive (spectate_app.run_interactive / interactive_app.
# run_interactive_attach) does before either ever touches a keystroke.
# Exits 0 iff that round-trip succeeds, 1 on any curses.error/OSError.
_PTY_CURSES_PROBE_SRC = (
    "import curses, sys\n"
    "def _check(stdscr):\n"
    "    pass\n"
    "try:\n"
    "    curses.wrapper(_check)\n"
    "except Exception:\n"
    "    sys.exit(1)\n"
    "sys.exit(0)\n"
)


@functools.lru_cache(maxsize=None)
def pty_curses_supported():
    """Functional capability probe for tests/test_control_panel.py and
    tests/test_interactive_app.py: can a subprocess spawned the exact
    way those tests spawn theirs (fresh pty via pty.openpty(), pty slave
    on stdin/stdout/stderr, start_new_session=True, TERM=xterm) actually
    initialize curses end-to-end? This is the real discriminator for the
    false-fail those tests hit in a headless/no-controlling-terminal
    environment (curses.wrapper()'s initscr()/cbreak() raising uncaught,
    or the process otherwise exiting nonzero) -- not a heuristic like
    os.isatty(0), which would wrongly skip in a pty-capable environment
    whose own stdin/stdout merely aren't a tty (true of a CI runner or an
    agent harness driving pytest, both of which still pass the real
    tests here). Computed once per test run and cached -- every calling
    test module shares the one result instead of re-probing.

    Must drain master_fd exactly like the real tests' pty drivers do
    (_drive_pty / _run_attach_in_pty): curses' own init/teardown escape
    sequences are only tens of bytes, but an undrained pty still blocks
    the child's write() (and therefore its exit) until a reader shows up
    -- discovered the hard way when an earlier plain proc.wait(timeout)
    version timed out and falsely reported "unsupported" in this very
    pty-capable environment."""
    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", _PTY_CURSES_PROBE_SRC],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            env=dict(os.environ, TERM="xterm"),
            start_new_session=True,
        )
        os.close(slave_fd)
        slave_fd = -1
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and proc.poll() is None:
            ready, _, _ = select.select([master_fd], [], [], 0.3)
            if master_fd in ready:
                try:
                    if not os.read(master_fd, 65536):
                        break
                except OSError:
                    break
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return proc.returncode == 0
    finally:
        if slave_fd != -1:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        try:
            os.close(master_fd)
        except OSError:
            pass
