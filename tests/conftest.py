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

# Shared in-process attach CLI fixtures (tty_fd); FakeAttachConn helpers live
# in attach_helpers.py and are imported by test_cli_attach_*.py directly.
pytest_plugins = ("tests.attach_helpers",)

from tw2002_aiclient.session import env as _env
from tw2002_aiclient.session.settle import MATCH_SCOPE_SCREEN

# Top-level import is safe here (no cycle): `pty_helpers` only imports THIS
# module lazily, inside `pty_curses_supported()`'s own function body, never
# at its own module load time.
from tests.pty_helpers import terminate_session_group

# Post-ADR-001, `twclient` relocated to `tw2002_aiclient.session` -- but
# control_lock/loop_player/watch haven't landed there yet (WO-P2-020
# Wave-4 only ports settle/classify's own dependency, env), and the
# ported Session is still missing the observe_*/*_snapshot methods
# FakeAttachSession assigns straight off the class body below (see
# .claude/agent-memory/monk/state-parser-not-yet-ported.md). Import
# what exists; anything that still 404s (or whose class shape is
# incomplete) falls back to a skip below rather than an
# ImportError-at-collection that would take test_settle.py/
# test_classify.py down with it -- this block re-arms itself the
# moment those modules/methods land, no further edit needed here.
try:
    from tw2002_aiclient.session.control_lock import ControlLock
    from tw2002_aiclient.session.daemon import CommandHandler, ThreadingUnixServer
    from tw2002_aiclient.session.watch import WatchHub

    _FAKE_DAEMON_IMPORTS_OK = True
except ImportError:
    _FAKE_DAEMON_IMPORTS_OK = False


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

    `observe_credits`/`credits_snapshot` (WO-FA-SAFE) are DELIBERATELY
    ABSENT from this shared base, even though `Session` grew both methods
    since (WO-P2-G4-X5, `tw2002_aiclient/session/session.py`). A test that
    needs the credits-floor behavior opts in by subclassing and assigning
    them itself straight off `Session` -- the convention
    `tests/test_autoloop.py`'s `WireSession` -> `tests/test_credits_floor.py`'s
    `CreditsWireSession` already uses (`observe_credits =
    Session.observe_credits`, same for `credits_snapshot`) -- rather than
    this base class growing them for every caller. The reason is a live
    negative case, not caution for its own sake:
    `tests/test_autoloop.py::test_a_floor_is_still_refused_when_this_session_cannot_enforce_it`
    asserts `not hasattr(session, "credits_snapshot")` on a plain
    `WireSession` to prove a session that genuinely cannot enforce a floor
    is refused rather than silently armed. A class attribute assigned here
    would be inherited by every subclass -- including that one -- turning
    a deliberate "this runtime cannot honour that" case into a session
    that silently can (confirmed by attaching the methods here and running
    that test: it fails on the hasattr assertion). Attach per-subclass,
    never on this shared base.
    `self.lock` is a plain `threading.Lock`, the same shape `Session.lock`
    is, already set below -- so a subclass that DOES assign the real
    methods (both of which acquire a lock internally) has one ready-made."""

    # observe_credits/credits_snapshot are intentionally NOT assigned here
    # (see the class docstring above) even though Session has had both
    # since WO-P2-G4-X5 -- tests/test_autoloop.py depends on this shared
    # fixture genuinely lacking them. A subclass that wants the real
    # behavior assigns its own, as tests/test_credits_floor.py's
    # CreditsWireSession does.

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
        # Pre-seed sticky HUD values so ensure's seed_hud_after_join does
        # not inject a spurious I-probe on every FakeAttachSession ensure
        # (WO-HUD-CREDITS-TURNS-JOIN). Tests that need a probe unset these.
        self.last_credits = 1000
        self.last_credits_ts = 0.0
        self.last_turns = 100
        self.last_turns_ts = 0.0
        self.last_turns_max = 100
        # Sticky fighters start unknown (None) — status intervention may
        # report fighters_unknown until an Info/HFS screen is observed.
        self.last_fighters = None
        self.last_fighters_ts = None
        # Mirrors Session.auto_login_profile / mark_profile — ensure's
        # already_there path now always stamps the profile so status
        # world_id resolves (WO-TUI-PRIORITIES-DECISIONS-REGRESS).
        self.auto_login_profile = None

    def mark_profile(self, profile_name):
        self.auto_login_profile = profile_name

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

    def wait_settle(
        self,
        wait_prompt=None,
        timeout=8.0,
        debounce_ms=350,
        prompt_requires_new_bytes=False,
        match_scope=MATCH_SCOPE_SCREEN,
    ):
        # WO-DO-SETTLE-RX-GUARD / WO-DO-PROMPT-LINE-PIN:
        # `prompt_requires_new_bytes` and `match_scope` mirror the real
        # Session.wait_settle signature -- protocol.py's `do` passes BOTH
        # on every call, so a double that omitted either would TypeError
        # the whole verb. Unused here: this stub returns a canned settle
        # rather than running wait_for_settle, so it has no prompt branch
        # to guard and no regex to place. Their real behaviour is proven
        # against a real Session in tests/test_do_settle_rx_guard.py.
        #
        # Note this double deliberately does NOT grow a
        # `current_prompt_line()` to match: because it never delegates to
        # `wait_for_settle`, `settle._match_source` is never reached, so
        # the accessor `match_scope="prompt_line"` would demand is never
        # asked for. A double that DOES delegate needs one.
        return "idle", 0.0

    def send(self, text, enter=True, secret=False, sender="app"):
        self.sent.append((text, enter, secret))
        self.last_sent = "<redacted>" if secret else text
        self.last_sent_ts = self.t
        self.last_sender = sender
        self._pending_advance = True

    def send_raw(self, data: bytes, control_lock=None, sender="human"):
        # Mirrors Session.send_raw signature (WO-CLEANPREEMPT + sender tag).
        if control_lock is not None:
            deadline = time.monotonic() + 10.0
            while control_lock.is_driver_fenced() and time.monotonic() < deadline:
                time.sleep(0.02)
        self.raw_sent.append(data)
        self.last_sent = data.decode("latin-1", errors="replace")
        self.last_sent_ts = self.t
        self.last_sender = sender
        self._pending_advance = True

    def record_history(self, verb, args, prompt, classification, settled_reason):
        """The same ENTRY SHAPE `Session.record_history` produces (WO-ARM-HISTORY-RING).

        This appended a 5-tuple until 2026-07-29, while the real session appends
        a dict with a `ts`. Nothing read it, so nothing was failing -- and that
        is exactly what made it dangerous: the first test to assert on history
        through this double would have been handed a shape the product never
        emits, and would have passed while pinning a fiction. Every existing
        reader (`test_cli_ops_verb_b/c`, `test_session`) subscripts by name
        because they all use the real `Session`; this double was the only
        producer of the tuple and had no consumer at all.

        The ring CAP is deliberately not modelled -- the real one trims at
        `_history_cap` and this does not. Anything asserting eviction belongs
        against the real session, not here.
        """
        self.history.append(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verb": verb,
                "args": args,
                "prompt": prompt,
                "classification": classification,
                "settled_reason": settled_reason,
            }
        )


class _FakeDaemon:
    """Real ThreadingUnixServer + CommandHandler + WatchHub against a
    FakeAttachSession — enough for attach/subscribe protocol proofs.
    LoopPlayer deferred (not required for F1 attach)."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self.session = FakeAttachSession()
        self.control_lock = ControlLock()
        self.watch_hub = WatchHub(self.session)
        self.server = ThreadingUnixServer(self.sock_path, CommandHandler)
        self.server.session = self.session
        self.server.control_lock = self.control_lock
        self.server.watch_hub = self.watch_hub
        self.server.request_stop = lambda: None
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.watch_hub.start()
        self._thread.start()

    def stop(self):
        self.watch_hub.stop()
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def fake_daemon():
    """Isolated fake daemon per test on a short /tmp unix socket path."""
    if not _FAKE_DAEMON_IMPORTS_OK:
        pytest.skip(
            "fake_daemon needs tw2002_aiclient.session.{control_lock,watch,daemon}"
        )
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
        terminate_session_group(proc)
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
