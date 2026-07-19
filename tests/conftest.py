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

import json
import os
import shutil
import socket
import tempfile
import threading
from pathlib import Path

import pytest

from twclient import env as _env
from twclient.control_lock import ControlLock
from twclient.daemon import CommandHandler, ThreadingUnixServer
from twclient.loop_player import LoopPlayer
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
    FakeLoginSession conventions."""

    def __init__(self, initial_screen="Command [TL=00:00:00]:[1234] (?=Help)? :"):
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
        self._cursor = {"x": 0, "y": 0}

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
        self.t += seconds

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return "idle", 0.0

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self.rx_count += 1
        self.last_rx = self.t
        self.last_sent = "<redacted>" if secret else text
        self.last_sent_ts = self.t

    def send_raw(self, data: bytes):
        self.raw_sent.append(data)
        self.rx_count += 1
        self.last_rx = self.t
        self.last_sent = data.decode("latin-1", errors="replace")
        self.last_sent_ts = self.t

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
