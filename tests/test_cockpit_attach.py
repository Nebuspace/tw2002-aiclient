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
import queue
import shutil
import tempfile
import threading
import time
from pathlib import Path

from tw2002_aiclient import adapters, app
from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.cockpit.control_seat import APP_LABEL, MANUAL_LABEL
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow
from tw2002_aiclient.session.attach_client import DETACH_KEY, AttachInputConn
from tw2002_aiclient.session.control_lock import ControlLock, MODE_APP, MODE_HUMAN
from tw2002_aiclient.watchfeed import WatchFeed

from .conftest import _FakeDaemon
from .test_cockpit_mode_badge import _control_strip_frame

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
    """Reconstruct the control-strip row's LAST-drawn frame as one string.

    WO-P5-060: the row is now drawn via `draw_segment_line`, which emits
    ONE `addstr` call PER SEGMENT (each segment carries its own curses
    attr, so they can't be combined into a single call) rather than the
    pre-existing single whole-line call `draw_lines` made -- so a bare
    `row_calls[-1]` (the old technique) now only sees the LAST segment
    (typically the liveness cluster), silently dropping the mode-badge
    label segment that precedes it. Every fresh `draw()` pass' leftmost
    write for this row always starts at the row's own left edge
    (`control_strip["x"]`, unboxed) -- whether via one fallback call or
    several segment calls -- so the LAST occurrence of that x-offset marks
    where the most recent frame's own writes begin; everything from there
    onward (this row's `calls` are appended in strict left-to-right
    cursor order within one frame) concatenates back into that frame's
    full visible row text, robust to however many `addstr` calls composed
    it."""
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    row_x = control_strip["x"]  # boxed=False -- no inset, this IS the write x
    row_calls = [(x, text) for (y, x, text, _a) in win.calls if y == control_strip["y"]]
    assert row_calls, "expected an addstr call on the control strip row"
    last_frame_start = max(i for i, (x, _t) in enumerate(row_calls) if x == row_x)
    return "".join(text for _x, text in row_calls[last_frame_start:])


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
        assert play.attached is True  # WO-P5-060 lane B: honest badge truth
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
        assert play.attached is False  # WO-P5-060 lane B: never falsely claimed
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
    assert play.attached is False  # WO-P5-060 lane B: honest badge truth, alongside spectating
    assert "attach connection lost" in play.status_line
    assert fake_conn.closed is True


def test_control_strip_transitions_spectate_manual_and_back(monkeypatch):
    """Addendum pin (Samantha): the TRANSITION, not just an end state --
    SPECTATE visible while spectating -> `MANUAL_LABEL` visible once
    attached -> back to SPECTATE once `spectating` is true again.
    WO-P4-054 taught us a one-way assertion can't prove a state surface
    actually returns. Driven directly via `PlayShellScreen.spectating`/
    `.attached` (not a real detach round trip through `app.py` -- the
    actual detach mechanism is WO-P4-057's, not built here). WO-P5-060:
    both fields are now driven together, mirroring how `app.py::_run_play`
    always sets them as a pair -- `spectating` alone no longer implies
    `attached`'s value (the pre-existing `attached=not self.spectating`
    derivation this WO's own call-site fix replaced)."""
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    win = _RecordingStdscr([])
    screen = PlayShellScreen(win, _profile())

    screen.draw()
    row1 = _control_strip_row_text(win)
    assert "SPECTATE" in row1
    assert MANUAL_LABEL not in row1

    win.calls.clear()
    screen.spectating = False
    screen.attached = True
    screen.draw()
    row2 = _control_strip_row_text(win)
    assert MANUAL_LABEL in row2
    assert "SPECTATE" not in row2

    win.calls.clear()
    screen.spectating = True
    screen.attached = False
    screen.draw()
    row3 = _control_strip_row_text(win)
    assert "SPECTATE" in row3
    assert MANUAL_LABEL not in row3


# ---------------------------------------------------------------------------
# WO-P4-057 -- graceful Ctrl-] detach: attached -> spectating, lock genuinely
# released daemon-side, further keys route back through play.handle_key.
#
# The plain list-driven `_RecordingStdscr` above is sufficient when a test
# only needs the FINAL state after a whole scripted key sequence runs to
# completion (`_run_play` doesn't return until "back"/"quit", so there is no
# way to pause mid-drive with a never-blocking fake without spinning). Some
# proofs below genuinely need to pause mid-drive -- e.g. "the lock is
# released" is asynchronous on the daemon's OWN reader thread noticing EOF,
# not synchronous with the client's `attach_conn.close()` -- so this section
# adds a blocking-queue stdscr variant and drives `_run_play` on a background
# thread, mirroring `test_run_play_m_attaches_forwards_a_keystroke_and_esc_
# releases`'s own bounded-poll idiom for daemon-side lock release, just
# interleaved with key pushes instead of asserted only once at the very end.
# ---------------------------------------------------------------------------


class _QueueStdscr:
    """Blocking-queue-driven fake stdscr -- `getch()` pulls from a
    `queue.Queue`, returning -1 (the existing "no key, redraw" tick,
    matching `_RecordingStdscr`'s exhausted-list behavior) on a short poll
    timeout rather than spinning forever waiting on a key nobody has pushed
    yet. Lets a driving THREAD sit genuinely parked between pushes so a
    test can pause mid-drive and poll condition-driven state (daemon lock
    mode, `play.spectating`, ...) before pushing the next key -- something
    the plain list-driven `_RecordingStdscr` above cannot do without
    spinning at 100% CPU on its own never-blocking `getch()`."""

    def __init__(self):
        self._q: "queue.Queue[int]" = queue.Queue()
        self.calls: list[tuple[int, int, str, int]] = []

    def push(self, key: int) -> None:
        self._q.put(key)

    def getch(self):
        try:
            return self._q.get(timeout=0.05)
        except queue.Empty:
            return -1

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


def _drive_run_play_in_thread(stdscr, profile):
    """Runs `app._run_play` on a background thread so a test can push keys
    and poll condition-driven state IN BETWEEN them. Returns ``(thread,
    result_box)`` -- ``result_box`` is populated with the single
    ``"back"``/``"quit"`` result once the thread finishes; the caller must
    push a terminating key and ``thread.join()`` itself."""
    result_box: list[str] = []

    def _run():
        result_box.append(app._run_play(stdscr, profile))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, result_box


def _wait_until(predicate, timeout=3.0, interval=0.02) -> bool:
    """Bounded condition-driven poll -- never a bare sleep standing in for
    a state transition. Returns the predicate's own final truthiness
    (never raises itself)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def _capture_watchfeed_instances(monkeypatch):
    """Spy on `WatchFeed.__init__`, mirroring `_capture_play_instances`
    above -- `_run_play` never exposes its `feed` instance externally."""
    captured: list[WatchFeed] = []
    orig_init = WatchFeed.__init__

    def _spy(self, *a, **k):
        orig_init(self, *a, **k)
        captured.append(self)

    monkeypatch.setattr(WatchFeed, "__init__", _spy)
    return captured


# --- Proof 1: detach happens ------------------------------------------------


def test_detach_key_flips_spectating_true_and_signals_detach_and_releases_lock(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: bool(captured)), "PlayShellScreen was never constructed"
        play = captured[-1]

        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.spectating is False), "M never attached"
        assert _wait_until(lambda: play.attached is True), "M never set attached True"
        assert daemon.control_lock.mode == MODE_HUMAN

        stdscr.push(DETACH_KEY)
        assert _wait_until(lambda: play.spectating is True), "Ctrl-] never detached"
        assert _wait_until(lambda: play.attached is False), "Ctrl-] never cleared attached"
        assert _wait_until(lambda: "detach" in play.status_line.lower()), (
            f"status line never signaled detach: {play.status_line!r}"
        )
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_APP), (
            f"daemon-side lock never released after detach (still {daemon.control_lock.mode!r})"
        )

        stdscr.push(27)  # Esc -- end the drive; already spectating, so this
        # is the ordinary back-to-launcher exit, not a second detach
        # (attach_conn is already None by this point).
        thread.join(timeout=3.0)
        assert result_box == ["back"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


# --- Proof 2: lock genuinely released -- a FRESH attach succeeds -----------


def test_detach_then_fresh_attach_succeeds_proving_lock_released(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: bool(captured))
        play = captured[-1]

        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.spectating is False)

        stdscr.push(DETACH_KEY)
        assert _wait_until(lambda: play.spectating is True)
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_APP)

        # Strongest form: a genuinely FRESH `_attempt_attach` (mirrors
        # Layer 2's own take/held/conflict proof above), independent of
        # this cockpit instance's own bookkeeping, succeeds immediately.
        # A not-raised assertion would not be enough -- only a SUCCESSFUL
        # independent re-acquire proves the daemon's own lock is free.
        fresh_conn, fresh_error = app._attempt_attach(daemon.sock_path)
        assert fresh_conn is not None, (
            f"reattach refused -- lock was never released ({fresh_error!r})"
        )
        fresh_conn.close()
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_APP), (
            "the probe's own close should release the lock again"
        )

        # And the cockpit's own second `M`, through the real product path,
        # succeeds too -- end to end, not just at the daemon.
        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.spectating is False), "re-attach via M never succeeded"
        assert _wait_until(lambda: "attached" in play.status_line.lower())

        stdscr.push(27)
        thread.join(timeout=3.0)
        assert result_box == ["back"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


# --- Proof 3: no send after detach; keys route back through handle_key -----


def test_no_send_after_detach_and_keys_route_through_handle_key_again(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: bool(captured))
        play = captured[-1]

        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.spectating is False)

        stdscr.push(ord("d"))  # baseline forwarded traffic while attached
        assert _wait_until(lambda: daemon.session.raw_sent == [b"d"])

        stdscr.push(DETACH_KEY)
        assert _wait_until(lambda: play.spectating is True)
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_APP)

        # Two keys, unmapped-then-quit -- `q` only ever resolves to "quit"
        # via `play.handle_key`; attach-forwarding never returns a "quit"
        # action (it `continue`s unconditionally). Observing "quit" is
        # therefore a deterministic proof BOTH keys re-entered the
        # handle_key path, at the exact synchronization point
        # (thread.join()) that also proves no further traffic arrived --
        # no bare sleep needed to "prove an absence".
        stdscr.push(ord("x"))  # unmapped -- a safe no-op probe
        stdscr.push(ord("q"))  # handle_key's quit shortcut
        thread.join(timeout=3.0)
        assert result_box == ["quit"]
        assert daemon.session.raw_sent == [b"d"], (
            f"unexpected post-detach wire traffic: {daemon.session.raw_sent!r}"
        )
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


# --- Proof 4: idempotent double-detach --------------------------------------


def test_double_detach_is_a_safe_no_op(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: bool(captured))
        play = captured[-1]

        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.spectating is False)

        stdscr.push(DETACH_KEY)
        assert _wait_until(lambda: play.spectating is True)
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_APP)
        status_after_first_detach = play.status_line

        # A second Ctrl-] while ALREADY spectating: `attach_conn` is
        # already `None` by construction, so this key falls through to
        # `play.handle_key(29)` -- unmapped, returns `None`, same as any
        # other stray key -- rather than re-running the detach branch at
        # all (that branch is gated on `attach_conn is not None`). No
        # exception, no further state change, no wire traffic.
        stdscr.push(DETACH_KEY)
        stdscr.push(ord("q"))  # deterministic sync point, see proof 3
        thread.join(timeout=3.0)
        assert result_box == ["quit"], "double-detach broke the drive thread"

        assert play.spectating is True
        assert play.attached is False  # WO-P5-060 lane B: unaffected by the no-op second detach
        assert play.status_line == status_after_first_detach
        assert daemon.control_lock.mode == MODE_APP
        assert daemon.session.raw_sent == []  # never any forwarded traffic at all
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_detach_after_broken_wire_fallback_is_also_a_safe_no_op(monkeypatch, tmp_path):
    """Proof 4 addendum: a Ctrl-] pressed AFTER an already-broken attach
    connection has fallen back to spectate (app.py's own `sent_ok=False`
    path, pinned by the sibling `test_run_play_broken_attach_connection_
    falls_back_to_spectate_honestly` above) must ALSO be a safe no-op --
    `attach_conn` is already `None` by the time DETACH_KEY is seen, so it
    takes the exact same `attach_conn is None` fall-through proved above,
    without needing a real daemon/threaded drive for this cheap variant."""

    class _FlakyConn:
        def __init__(self):
            self.closed = False

        def send_key(self, data):
            return False  # every forward fails

        def close(self):
            self.closed = True

    fake_conn = _FlakyConn()
    monkeypatch.setattr(app, "_attempt_attach", lambda sock_path: (fake_conn, None))
    monkeypatch.setenv("TW_RUN_DIR", str(tmp_path))  # no daemon -- WatchFeed's own connect fails, contained
    _patch_common(monkeypatch)
    captured = _capture_play_instances(monkeypatch)

    stdscr = _RecordingStdscr([ord("M"), ord("d"), DETACH_KEY, 27])
    result = app._run_play(stdscr, _profile())
    assert result == "back"

    play = captured[-1]
    assert play.spectating is True
    assert play.attached is False  # WO-P5-060 lane B: still false after the no-op Ctrl-]
    assert play.status_line == "attach connection lost — spectating"
    assert fake_conn.closed is True


# --- Proof 5: Esc is not detach ---------------------------------------------


def test_esc_is_not_detach_still_ends_the_binding_via_finally_release(monkeypatch):
    """Regression pin: Esc (27) stays the pre-existing, DIFFERENT exit --
    it ends the whole play-shell binding (`_run_play` returns `"back"`),
    not merely a detach back to spectate, and the daemon-side lock is
    still released through the `finally` block's own `attach_conn.close()`
    (WO-P4-056's mechanism), never through DETACH_KEY's dedicated branch."""
    assert DETACH_KEY != 27  # the two exits must never collide

    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _RecordingStdscr([ord("M"), 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"

        play = captured[-1]
        # Esc's own status_line is still whatever the earlier `M` set --
        # never overwritten by a detach-style message, because
        # DETACH_KEY's branch never ran.
        assert "attached" in play.status_line.lower()
        assert "detach" not in play.status_line.lower()

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and daemon.control_lock.mode == MODE_HUMAN:
            time.sleep(0.02)
        assert daemon.control_lock.mode == MODE_APP  # released via finally, same as WO-P4-056
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


# --- Proof 6: control-strip chip restores to SPECTATE after detach ---------


def test_control_strip_chip_restores_to_spectate_after_detach(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)

        stdscr = _RecordingStdscr([ord("M"), DETACH_KEY, 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"

        row_text = _control_strip_row_text(stdscr)  # LAST control-strip draw
        assert "SPECTATE" in row_text
        assert MANUAL_LABEL not in row_text
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


# --- Proof 7: the WatchFeed / viewport wiring survives detach untouched ----


def test_watchfeed_survives_detach_still_running_and_provider_still_bound(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured_plays = _capture_play_instances(monkeypatch)
        captured_feeds = _capture_watchfeed_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: captured_plays and captured_feeds)
        play = captured_plays[-1]
        feed = captured_feeds[-1]

        assert _wait_until(lambda: feed.snapshot().running is True), (
            "WatchFeed never came up before the drive could proceed"
        )

        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.spectating is False)

        stdscr.push(DETACH_KEY)
        assert _wait_until(lambda: play.spectating is True)
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_APP)

        # Proven WHILE the drive thread is still parked inside the loop --
        # not after teardown, where `finally: feed.stop()` would trivially
        # make `running` False regardless of what detach itself did.
        assert feed.snapshot().running is True
        # `==`, not `is` -- a bound method (`feed.snapshot`) is a fresh
        # wrapper object on every attribute access, so identity comparison
        # is almost always False even for the SAME underlying instance
        # method; bound methods implement `__eq__` to compare `__self__`
        # + `__func__`, which is the actual "still the same binding" proof.
        assert play.viewport_provider == feed.snapshot
        assert play.viewport_provider.__self__ is feed  # and explicitly the same feed instance

        stdscr.push(27)
        thread.join(timeout=3.0)
        assert result_box == ["back"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# WO-P5-061 -- App-hold kernel: prove App-hold (`spectating=False,
# attached=False` -- the 060 strict gate's one legitimate case) is a real,
# correctly-behaving client state and pin every ruled transition around it.
#
# The Human->App-hold ENTRY trigger (Accept #2) is PARKED pending a Max
# ruling -- nothing below builds, reserves a key, or invents a UI path for
# it. Every test that needs to START in App-hold gets there the same way:
# driving `play.spectating`/`play.attached` directly, exactly like the
# pre-existing `test_control_strip_transitions_spectate_manual_and_back`
# above already does for its own spectate<->manual walk -- the driven state
# is the honest mechanism, not a claim that a real keypress reaches it today.
# ---------------------------------------------------------------------------


def test_app_hold_daemon_seat_truth_default_mode_is_app_not_a_client_fiction():
    """Kernel item 1: control_lock.py's own default construction is
    ``self._mode = MODE_APP`` (``control_lock.py:59``), and
    ``app_may_send()`` (``control_lock.py:75-82``) reads ``True`` the
    instant ``mode == MODE_APP`` -- that method's own docstring: "Spectate
    and Human never grant App send." With no ``take_human()`` ever called
    and no ``enter_auto_loop()`` hold taken, ``MODE_APP`` is the daemon's
    OWN standing seat-holder default, not a client-side invention. The
    client's App-hold mirror (``spectating is False and attached is
    False``, the exact pair ``cockpit.control_seat.py``'s
    ``_is_definitively_false`` gate requires before it will render the
    ``APP_LABEL`` chip at all -- see that module's own
    ``_resolve_label_and_tone`` docstring) is therefore an honest
    reflection of a real daemon-side fact, not a client fiction."""
    lock = ControlLock()
    assert lock.mode == MODE_APP
    assert lock.app_may_send() is True


def test_app_hold_m_attaches_to_human_lock_and_manual_chip_renders(monkeypatch):
    """Accept #1 (WO-P5-061): from App-hold (driven directly -- Accept #2's
    ENTRY trigger is parked, see this section's own header comment), `M`
    still reaches the exact same ``_attempt_attach`` path the shipped
    Spectate->Human leg uses (``test_run_play_m_attaches_forwards_a_
    keystroke_and_esc_releases`` above): ``PlayShellScreen.handle_key``
    returns ``"attach"`` for `M`/`m` unconditionally, never gated on
    ``self.spectating``/``self.attached`` (``screens.py::handle_key``), and
    ``app.py::_run_play``'s own action handler only checks
    ``attach_conn is None`` before calling ``_attempt_attach`` -- also
    state-independent. Pins the daemon-side lock flip AND the rendered
    MANUAL chip (warn + bold + reverse, the 060 attr path) together, not
    just the label."""
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: bool(captured)), "PlayShellScreen was never constructed"
        play = captured[-1]

        # Drive to App-hold directly (Accept #2's entry is parked).
        play.spectating = False
        play.attached = False
        assert daemon.control_lock.mode == MODE_APP  # daemon-side default, unaffected by the client-only flip

        stdscr.push(ord("M"))
        assert _wait_until(lambda: play.attached is True), "M never attached from App-hold"
        assert _wait_until(lambda: play.spectating is False)
        assert _wait_until(lambda: daemon.control_lock.mode == MODE_HUMAN), (
            "daemon-side lock never flipped to MODE_HUMAN from the App-hold M press"
        )
        assert "attached" in play.status_line

        frame = _control_strip_frame(stdscr, FULL_ROWS, FULL_COLS)
        joined = "".join(text for text, _attr in frame)
        assert APP_LABEL not in joined  # App chip must not survive the attach
        assert MANUAL_LABEL in joined
        label_text, label_attr = frame[0]
        assert label_text.startswith(MANUAL_LABEL)
        assert label_attr == curses.A_BOLD | curses.A_REVERSE  # mono path -- _patch_common forces has_colors False

        stdscr.push(27)
        thread.join(timeout=3.0)
        assert result_box == ["back"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_ctrl_bracket_from_app_hold_is_a_no_op_state_unchanged_unruled_edge(monkeypatch):
    """Accept #4 (WO-P5-061): Ctrl-] FROM App-hold is currently UNRULED --
    canon `spectate-and-attach.md:100-102` only names Ctrl-] as the
    detach-while-attached affordance; it says nothing about App-hold (a
    state canon does not yet define an ENTRY trigger for -- Accept #2,
    PARKED). This test PINS the current, accidental behavior rather than a
    designed one: with no attach ever taken, `attach_conn is None`, so
    `_run_play`'s own `if attach_conn is not None and key != 27:` guard
    (`app.py:266`) is False and the key falls all the way through to
    `play.handle_key(29)` -- which has no branch for 29 at all
    (`screens.py::handle_key` only matches 27/q/Q/M/m) -- returning
    `None`, an ordinary unmapped-key no-op, identical in mechanism to the
    already-shipped `test_double_detach_is_a_safe_no_op`'s second Ctrl-]
    (that one from Spectate, this one from App-hold). If canon later rules
    a distinct Ctrl-] meaning from App-hold, THIS test's own future
    failure is the deliberate tripwire that forces the change to be
    reviewed, not silently absorbed."""
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _QueueStdscr()
        thread, result_box = _drive_run_play_in_thread(stdscr, _profile())
        assert _wait_until(lambda: bool(captured))
        play = captured[-1]
        # Wait for the constructor-time transient ("Ensuring session…") to
        # settle before capturing the baseline -- the drive thread keeps
        # running concurrently past `_wait_until(lambda: bool(captured))`,
        # so a bare read right after that would race `_run_play`'s own
        # post-`ensure_session()` status_line write.
        assert _wait_until(lambda: play.status_line not in ("", "Ensuring session…"))

        play.spectating = False
        play.attached = False
        status_before = play.status_line

        stdscr.push(DETACH_KEY)
        stdscr.push(ord("q"))  # deterministic sync point, mirrors proof 3/4's own idiom above
        thread.join(timeout=3.0)
        assert result_box == ["quit"]

        assert play.spectating is False  # unchanged
        assert play.attached is False  # unchanged
        assert play.status_line == status_before  # no status mutation either
        assert daemon.control_lock.mode == MODE_APP  # nothing was ever taken
        assert daemon.session.raw_sent == []  # no wire traffic
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)
