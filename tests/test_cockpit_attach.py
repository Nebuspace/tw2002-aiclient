"""WO-P4-056 lane A -- `M` attaches the cockpit to the daemon's Human
control lock (canon `mode-line-and-teach-controls.md:40-47`).

Three layers, mirroring `tests/test_spectate_no_send.py`'s own shape:

  1. Pure `PlayShellScreen.handle_key` proof -- `M`/`m` signal INTENT only
     (`"attach"`); this class has no daemon I/O of its own (see `tests/
     test_spectate_no_send.py`'s guards) -- `app.py` is what acts on it.
  2. `app._attempt_attach` FakeClient proof against the `fake_daemon`
     fixture (`conftest.py`) -- the take/held/conflict/not-running
     control-lock transitions, using the REAL `AttachInputConn` + REAL
     daemon `_handle_attach` + REAL `ControlLock`, no curses involved.
  3. `app._run_play` end-to-end drives against a `_FakeDaemon` (conftest's
     own production-code-backed harness, imported directly rather than
     duplicated) rooted at a short `TW_RUN_DIR`/`twd.sock` -- the exact
     filename `env.socket_path()` resolves via `TW_RUN_DIR`, so the REAL
     run-dir resolution path is exercised end-to-end, not bypassed.
     Proves the `M` keypress reaches the daemon, `spectating` flips, the
     control-strip's SPECTATE chip drops and the `MANUAL_LABEL` badge
     appears (``screens.py``'s ``attached=not self.spectating`` wiring),
     an ordinary forwarded keystroke lands in the fake session's
     `raw_sent`, a refusal is surfaced honestly (never silently treated
     as success), and a broken mid-session connection falls back to
     spectate rather than pretending the human still holds the lock.

Esc/detach is explicitly OUT of scope (WO-P4-057, not built here). These
tests pin that Esc (27) ALONE keeps its PRE-EXISTING play-shell-exit
meaning even while attached -- the one interim safety exit this WO relies
on -- and that EVERY OTHER key, `q`/`Q` included, is a live game keystroke
once attached: canon `mode-line-and-teach-controls.md:42-44` -- "the
human always wins the keyboard" -- so reserving ordinary letters would be
a real loss of control fidelity, not a theoretical one (Samantha REVISE,
WO-P4-056). A real in-cockpit graceful detach affordance (canon
`spectate-and-attach.md:350` cites the archive's `Ctrl-]` precedent) is
WO-P4-057's job, never invented here.
"""

from __future__ import annotations

import curses
import shutil
import tempfile
import time
from pathlib import Path

from tw2002_aiclient import adapters, app
from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.cockpit.control_seat import MANUAL_LABEL
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow
from tw2002_aiclient.session.attach_client import AttachInputConn
from tw2002_aiclient.session.control_lock import MODE_APP, MODE_HUMAN

from .conftest import _FakeDaemon

HANDLE = "Alpha"
FULL_ROWS, FULL_COLS = 40, 160


def _profile() -> ProfileRow:
    return ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B",
    )


# ---------------------------------------------------------------------------
# 1. PlayShellScreen.handle_key -- pure intent signal, no daemon I/O.
# ---------------------------------------------------------------------------


def test_handle_key_m_signals_attach_intent():
    screen = PlayShellScreen.__new__(PlayShellScreen)
    assert screen.handle_key(ord("M")) == "attach"
    assert screen.handle_key(ord("m")) == "attach"


def test_handle_key_unrelated_keys_unaffected_by_m_addition():
    screen = PlayShellScreen.__new__(PlayShellScreen)
    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("Q")) == "quit"
    assert screen.handle_key(ord("x")) is None


# ---------------------------------------------------------------------------
# 2. app._attempt_attach -- FakeClient proof of the control-lock
#    transitions: take -> held -> conflict (refused, never queued).
# ---------------------------------------------------------------------------


def test_attempt_attach_take_held_conflict_path(fake_daemon):
    assert fake_daemon.control_lock.mode == MODE_APP  # standing state

    conn1, error1 = app._attempt_attach(fake_daemon.sock_path)
    assert conn1 is not None
    assert error1 is None
    assert fake_daemon.control_lock.mode == MODE_HUMAN  # take -> held

    conn2, error2 = app._attempt_attach(fake_daemon.sock_path)
    assert conn2 is None
    assert error2 == "already_attached"  # conflict -- refused, never queued
    assert fake_daemon.control_lock.mode == MODE_HUMAN  # first holder unaffected

    conn1.close()


def test_attempt_attach_daemon_not_running_is_handled_honestly(tmp_path):
    conn, error = app._attempt_attach(tmp_path / "no-such.sock")
    assert conn is None
    assert error  # some real, non-empty reason -- never silently None/success


# ---------------------------------------------------------------------------
# 3. app._run_play end-to-end -- real production daemon code
#    (conftest.py's _FakeDaemon) rooted at <tmp_path>/twd.sock so the REAL
#    env.socket_path()/TW_RUN_DIR resolution path is exercised.
# ---------------------------------------------------------------------------


class _RecordingStdscr:
    """Drivable fake stdscr -- getch/timeout (mirrors `tests/
    test_spectate_no_send.py`'s `_ScriptedStdscr`) PLUS addstr recording
    (mirrors `tests/test_cockpit_spectate.py`'s `_RecordingWin`), so one
    drive proves BOTH that `spectating` flips in memory AND that the
    control-strip's SPECTATE chip actually drops on screen."""

    def __init__(self, keys):
        self._keys = list(keys)
        self.calls: list[tuple[int, int, str, int]] = []

    def getch(self):
        return self._keys.pop(0) if self._keys else -1

    def timeout(self, _ms):
        return None

    def getmaxyx(self):
        return (FULL_ROWS, FULL_COLS)

    def erase(self):
        return None

    def addstr(self, y, x, text, attr=0):
        self.calls.append((y, x, text, attr))

    def refresh(self):
        return None


def _control_strip_row_text(win) -> str:
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    row_calls = [text for (y, _x, text, _a) in win.calls if y == control_strip["y"]]
    assert row_calls, "expected an addstr call on the control strip row"
    return row_calls[-1]


def _capture_play_instances(monkeypatch):
    """Spy on PlayShellScreen.__init__ so a test can inspect the ONE
    instance app._run_play constructs internally (never exposed via
    _run_play's own return value -- only ``"back"``/``"quit"``)."""
    captured: list[PlayShellScreen] = []
    orig_init = PlayShellScreen.__init__

    def _spy(self, *a, **k):
        orig_init(self, *a, **k)
        captured.append(self)

    monkeypatch.setattr(PlayShellScreen, "__init__", _spy)
    return captured


def _patch_common(monkeypatch):
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda *a, **k: EnsureResult(ok=True, classification="main_command"),
    )


def _short_run_dir() -> Path:
    """A SHORT temp dir (mirrors `conftest.py`'s own `fake_daemon` fixture,
    `tempfile.mkdtemp(prefix="twd-test-")`) rather than pytest's own
    `tmp_path` -- `tmp_path` nests under `.../pytest-of-<user>/pytest-N/
    <full test name>/`, long enough that `<that>/twd.sock` overflows
    AF_UNIX's ~104-byte `sun_path` limit (reproduced: `OSError: AF_UNIX
    path too long` on `ThreadingUnixServer.server_bind`). Caller owns
    cleanup (`shutil.rmtree(..., ignore_errors=True)`)."""
    return Path(tempfile.mkdtemp(prefix="twd-attach-"))


def test_run_play_m_attaches_forwards_a_keystroke_and_esc_releases(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _RecordingStdscr([ord("M"), ord("d"), 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"

        play = captured[-1]
        assert play.spectating is False
        assert "attached" in play.status_line

        row_text = _control_strip_row_text(stdscr)
        assert "SPECTATE" not in row_text  # chip dropped once attached
        assert MANUAL_LABEL in row_text  # and the Human badge takes its place

        assert daemon.session.raw_sent == [b"d"]  # the one forwarded keystroke

        # Esc closed attach_conn in _run_play's own `finally` -- the
        # daemon's `_handle_attach` releases the lock once it notices the
        # socket dropped (async on the daemon's own thread); poll briefly,
        # mirroring tests/test_attach_protocol.py's own idiom.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and daemon.control_lock.mode == MODE_HUMAN:
            time.sleep(0.02)
        assert daemon.control_lock.mode == MODE_APP
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_forwards_q_and_shift_q_while_attached_only_esc_reserved(monkeypatch):
    """Regression pin (Samantha REVISE, WO-P4-056): canon `mode-line-and-
    teach-controls.md:42-44` -- "the human always wins the keyboard" the
    instant they're attached, so `q`/`Q` are ordinary game keystrokes once
    attached, not a reserved app-quit shortcut. Esc (27) alone is the
    interim safety exit; the real detach affordance is WO-P4-057's
    (`spectate-and-attach.md:350` cites the archive's `Ctrl-]` precedent
    as what it should build toward, not `q`/`Q`)."""
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)

        stdscr = _RecordingStdscr([ord("M"), ord("q"), ord("Q"), 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == [b"q", b"Q"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_forwards_backspace_in_every_raw_form_as_canonical_bs(monkeypatch):
    """Hub ruling (WO-P4-056 REVISE): backspace forwarding is mandatory,
    not a disclosed gap -- a human who can't correct a typo while
    attached is materially impaired. Which raw form `getch()` yields is
    terminal/terminfo dependent (curses.KEY_BACKSPACE, raw DEL 0x7F, or
    raw BS 0x08); all three must canonicalize to the ONE byte the
    archive's own curses-attach precedent already established
    (`archive/pre-rebirth-2026-07-23/code/twclient/interactive_app.py::
    _encode_key`), never assumed."""
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)

        stdscr = _RecordingStdscr(
            [ord("M"), curses.KEY_BACKSPACE, 127, 8, 27]
        )
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == [b"\x08", b"\x08", b"\x08"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_attach_refusal_is_honest_not_silent_success(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        # Pre-attach from OUTSIDE the cockpit -- the cockpit's own M press
        # must be refused, not silently treated as success.
        blocker = AttachInputConn(daemon.sock_path)
        assert blocker.connect() is True

        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _RecordingStdscr([ord("M"), 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"

        play = captured[-1]
        assert play.spectating is True  # refusal never flips it
        assert "attach refused" in play.status_line
        assert "already_attached" in play.status_line

        row_text = _control_strip_row_text(stdscr)
        assert "SPECTATE" in row_text  # chip never dropped
        assert MANUAL_LABEL not in row_text  # Human badge never falsely claimed

        assert daemon.session.raw_sent == []  # nothing was ever forwarded

        blocker.close()
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_broken_attach_connection_falls_back_to_spectate_honestly(monkeypatch, tmp_path):
    """A mid-session forward failure (broken pipe, daemon gone, ...) must
    not leave the cockpit silently claiming the human still has control --
    see app.py's own comment at this fallback for why this is failure
    containment, not a WO-P4-057 detach decision."""

    class _FlakyConn:
        def __init__(self):
            self.closed = False

        def send_key(self, data):
            return False  # every forward fails

        def close(self):
            self.closed = True

    fake_conn = _FlakyConn()
    monkeypatch.setattr(app, "_attempt_attach", lambda sock_path: (fake_conn, None))
    monkeypatch.setenv("TW_RUN_DIR", str(tmp_path))  # no daemon here -- WatchFeed's own connect fails, contained
    _patch_common(monkeypatch)
    captured = _capture_play_instances(monkeypatch)

    stdscr = _RecordingStdscr([ord("M"), ord("d"), 27])
    result = app._run_play(stdscr, _profile())
    assert result == "back"

    play = captured[-1]
    assert play.spectating is True  # fell back, not stuck "attached"
    assert "attach connection lost" in play.status_line
    assert fake_conn.closed is True


def test_control_strip_transitions_spectate_manual_and_back(monkeypatch):
    """Addendum pin (Samantha): the TRANSITION, not just an end state --
    SPECTATE visible while spectating -> `MANUAL_LABEL` visible once
    attached -> back to SPECTATE once `spectating` is true again.
    WO-P4-054 taught us a one-way assertion can't prove a state surface
    actually returns. Driven directly via `PlayShellScreen.spectating`
    (not a real detach round trip through `app.py` -- the actual detach
    mechanism is WO-P4-057's, not built here)."""
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    win = _RecordingStdscr([])
    screen = PlayShellScreen(win, _profile())

    screen.draw()
    row1 = _control_strip_row_text(win)
    assert "SPECTATE" in row1
    assert MANUAL_LABEL not in row1

    win.calls.clear()
    screen.spectating = False
    screen.draw()
    row2 = _control_strip_row_text(win)
    assert MANUAL_LABEL in row2
    assert "SPECTATE" not in row2

    win.calls.clear()
    screen.spectating = True
    screen.draw()
    row3 = _control_strip_row_text(win)
    assert "SPECTATE" in row3
    assert MANUAL_LABEL not in row3
