"""WO-P3-041 wire -- LOGS band advancing transcript tail + newest-row flash,
Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
LOGS band ``screens.py``/``app.py`` produce once wired to
``cockpit.logsband``: the box shows the daemon's ``status["log_tail"]``
content (not just the bare box title), the tail genuinely ADVANCES across
draws as new lines arrive, a redacted-secret marker renders while a
sentinel planted in an UNRELATED status field never reaches the LOGS band's
own drawn row, the honest-empty/``status_line`` fallback still works with
no ``log_tail`` field at all, Esc/q regression is unchanged, and a hostile
control-char payload inside a tail entry is neutralized by the shared draw
choke point the same way ``tests/test_cockpit_frame_pty.py`` already proves
for ``status_line``. Layer-A coverage for the composer itself
(``compose_logs_lines``/``newest_tail_entry``/``flash_active``) lives in
``tests/test_cockpit_logsband.py``; this file only proves the
``PlayShellScreen``/``app.py`` wiring around it -- mirrors
``tests/test_cockpit_hud_pty.py``'s split for HUD.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process (same convention as every sibling cockpit-panel pty suite), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory -- the
real ``status_provider`` (``app._daemon_status_provider``) is free to run
unstubbed against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) for the no-fixture
scenario, and every other fixture additionally monkeypatches
``tw2002_aiclient.session.cli.send_request`` inside the bootstrap -- never
``run/twd.sock`` either way.

Advancing-tail proof, and why it does NOT wait for an exact line number:
the stubbed ``send_request``'s ``"status"`` verb keeps a module-level call
counter inside the spawned subprocess and grows ``log_tail`` by one entry
each time it is polled. ``app.py``'s own ``_run_play`` calls ``draw()``
TWICE back-to-back before the loop's first real ~1Hz tick (once showing
"Ensuring session…", once right after the stubbed ``ensure_session``
returns) -- so waiting for an EXACT early number (e.g. "line-1") is racy
against however much of that back-to-back pair the outer poll loop
actually observes as a distinct frame. Instead this file waits for the
generic marker substring, extracts whatever number is CURRENTLY showing,
waits several more real ticks, and asserts the SECOND number is strictly
greater than the first -- proving genuine advancement over wall-clock time
without depending on exact draw-count alignment (the general shape of the
"WO-P3-038/039 lesson": never assert on a specific-but-fragile transition
when a monotonic/structural one is available).

Newest-row flash proof, and why it is NOT racy against
``TICKER_FLASH_DURATION_S``: because THIS fixture's tail grows by exactly
one entry on every single poll, EVERY draw against it introduces a
genuinely NEW newest entry -- so at the exact draw() call that writes it,
``arrival_s`` and ``now`` are the SAME reading (age 0), deterministically
bold, regardless of real wall-clock scheduling. Any capture taken while
this fixture is still advancing therefore shows the newest row bold. The
CONTRASTING negative case (a STATIC tail, captured well after its one-time
arrival has aged past 1.0s) proves the flash does NOT stick.
"""

from __future__ import annotations

import os
import pty
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


import curses

from tw2002_aiclient.cockpit.layout import frame_layout

from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    pyte_screen,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Full tier -- matches every sibling cockpit-panel pty suite's own FULL
# constants so the LOGS band's one content row is unambiguously visible.
FULL_ROWS, FULL_COLS = 40, 160

_SECRET_MARKER = "<<secret input redacted>>"  # tw2002_aiclient.session.transcript_tail.TranscriptTail.append_redacted()'s own default wire format
_SECRET_SENTINEL = "SENTINEL-hunter2-SENTINEL"
_ADVANCING_RE = re.compile(r"advancing-line-(\d+)")

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as every sibling cockpit-panel pty suite's own bootstrap. The
# "advancing" fixture keeps its own per-process call counter so log_tail
# genuinely GROWS between polls (real ~1Hz redraw ticks -- see the module
# docstring).
_BOOTSTRAP = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, {project_root!r})

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification="main_command")


adapters.ensure_session = _fake_ensure

_LOGS_FIXTURE = os.environ.get("TW2002_TEST_LOGS_FIXTURE", "")
if _LOGS_FIXTURE:
    from tw2002_aiclient.session import cli as session_cli

    _state = {{"calls": 0}}

    def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        if verb != "status":
            return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}
        _state["calls"] += 1
        n = _state["calls"]

        if _LOGS_FIXTURE == "advancing":
            # Grows by one real entry every poll -- newest is always
            # "advancing-line-{{n}}", strictly larger than the previous
            # poll's, so every draw against this fixture is a fresh
            # arrival (see module docstring's flash-proof rationale).
            tail = [f"advancing-line-{{i}}" for i in range(1, n + 1)]
            return {{"ok": True, "connected": True, "idle_ms": 100, "log_tail": tail}}
        if _LOGS_FIXTURE == "static":
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 100,
                "log_tail": ["static-tail-line"],
            }}
        if _LOGS_FIXTURE == "secret":
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 100,
                "log_tail": ["before-secret", {secret_marker!r}],
                # Sentinel planted in an UNRELATED status field -- never
                # part of log_tail -- proving it cannot leak into the LOGS
                # band's own drawn row even though it rides the same
                # status payload.
                "prompt": {secret_sentinel!r},
            }}
        if _LOGS_FIXTURE == "hostile_control_chars":
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 100,
                "log_tail": ["before\nBREAKOUT-AFTER-NEWLINE"],
            }}
        return {{"ok": False, "error": "unknown_test_fixture"}}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
""".replace("{secret_marker!r}", repr(_SECRET_MARKER)).replace(
    "{secret_sentinel!r}", repr(_SECRET_SENTINEL)
)


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining ``master_fd`` for ``seconds`` of wall time, accumulating
    onto ``captured`` -- a single post-condition ``read()`` isn't reliable
    (``PlayShellScreen.draw()``'s one ``refresh()`` call still spans
    multiple OS-level pty read chunks for a full frame; LOGS is drawn near
    the end of the pass), same helper shape as
    ``tests/test_cockpit_liveness_pty.py``/``tests/test_cockpit_tones_pty.py``'s
    own ``_settle``.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured += chunk
    return captured


def _spawn(tmp_path: Path, bootstrap_name: str, fixture: str) -> tuple[subprocess.Popen, int]:
    bootstrap = tmp_path / bootstrap_name
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, FULL_ROWS, FULL_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if fixture:
        env["TW2002_TEST_LOGS_FIXTURE"] = fixture
    else:
        env.pop("TW2002_TEST_LOGS_FIXTURE", None)
    env.pop("TW2002_ASCII", None)
    env.pop("TW2002_HANDOFF_SMOKE", None)
    env.pop("TW2002_LAUNCHER_SMOKE", None)
    env.pop("TW2002_BANK_SMOKE", None)

    proc = subprocess.Popen(
        [sys.executable, str(bootstrap)],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(PROJECT_ROOT),
        env=env,
        start_new_session=True,
    )
    os.close(slave_fd)
    return proc, master_fd


def _teardown(proc: subprocess.Popen, master_fd: int, captured: bytes) -> bytes:
    drain_deadline = time.monotonic() + 5.0
    while time.monotonic() < drain_deadline and proc.poll() is None:
        ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured += chunk
    terminate_session_group(proc)
    try:
        os.close(master_fd)
    except OSError:
        pass
    return captured


def _drive_logs_pty(
    tmp_path: Path, *, ready_text: str, fixture: str = "", timeout: float = 14.0
) -> bytes:
    """Spawn ``app._run`` in a ``FULL_ROWS``x``FULL_COLS`` pty: Enter from
    the launcher once its chrome is up, capture the play-shell cockpit
    frame once ``ready_text`` is visible ANYWHERE on screen (letting at
    least one ~1 Hz refresh tick fully settle after that), then quit.

    ``ready_text`` must be real fixture CONTENT (a distinguishing tail
    line), never the bare "LOGS"/"PLAY SHELL" box title, which paints on
    the FIRST frame regardless of whether the status_provider's data has
    reached the composer yet (the WO-P3-038/039 lesson, mirrored from
    ``tests/test_cockpit_tones_pty.py``'s own ``_drive_tone_pty``).

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    so the real (unstubbed) status_provider path can never reach the
    project's own ``run/twd.sock`` regardless of which fixture is active.
    """
    proc, master_fd = _spawn(
        tmp_path, f"logs_pty_bootstrap_{fixture or 'none'}.py", fixture
    )

    captured = b""
    phase = "wait_launcher"
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk

            grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, ready_text):
                    captured = _settle(master_fd, captured, 1.6)
                    os.write(master_fd, b"q")
                    phase = "done"
                    break
        if phase != "done":
            try:
                os.write(master_fd, b"q")
            except OSError:
                pass
    finally:
        captured = _teardown(proc, master_fd, captured)

    assert phase == "done", (
        f"pty logs drive stalled in phase={phase!r} fixture={fixture!r}; "
        "last grid:\n" + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return captured


def _drive_advancing_logs_pty(tmp_path: Path, timeout: float = 16.0) -> tuple[bytes, bytes]:
    """Spawn ``app._run`` with the "advancing" fixture. Captures an EARLY
    frame (shortly after the first ``advancing-line-N`` marker appears,
    with only a short 0.5s settle -- comfortably under
    ``TICKER_FLASH_DURATION_S`` so this capture's own newest row is still a
    genuinely fresh arrival) and a LATER frame (after several more real
    ~1Hz ticks), both independently replayable -- see the module
    docstring's rationale for extracting NUMBERS rather than waiting on an
    exact early line's text.
    """
    proc, master_fd = _spawn(tmp_path, "logs_pty_bootstrap_advancing.py", "advancing")

    captured = b""
    capture_early: bytes | None = None
    capture_later: bytes | None = None
    phase = "wait_launcher"
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk

            grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_first"
            elif phase == "wait_first":
                if find_text(grid, "advancing-line-"):
                    captured = _settle(master_fd, captured, 0.5)
                    capture_early = captured
                    phase = "wait_growth"
            elif phase == "wait_growth":
                # Several more real ~1Hz ticks -- proves genuine
                # advancement over wall-clock time.
                captured = _settle(master_fd, captured, 2.5)
                capture_later = captured
                os.write(master_fd, b"q")
                phase = "done"
                break
        if phase != "done":
            try:
                os.write(master_fd, b"q")
            except OSError:
                pass
    finally:
        captured = _teardown(proc, master_fd, captured)

    assert phase == "done" and capture_early is not None and capture_later is not None, (
        f"pty advancing-logs drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return capture_early, capture_later


def _extract_advancing_number(row_text: str) -> int | None:
    m = _ADVANCING_RE.search(row_text)
    return int(m.group(1)) if m else None


@pytest.fixture(scope="module")
def _no_daemon_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_no_daemon")
    # No fixture -> status_provider resolves to None (daemon_not_running,
    # never touching run/twd.sock) -> no real tail -> the status_line
    # fallback (the real app._run_play flow sets
    # status_line = f"session ready — {classification}").
    return _drive_logs_pty(tmp_path, ready_text="session ready")


@pytest.fixture(scope="module")
def _static_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_static")
    return _drive_logs_pty(tmp_path, ready_text="static-tail-line", fixture="static")


@pytest.fixture(scope="module")
def _advancing_captures(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_advancing")
    return _drive_advancing_logs_pty(tmp_path)


@pytest.fixture(scope="module")
def _secret_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_secret")
    return _drive_logs_pty(tmp_path, ready_text=_SECRET_MARKER, fixture="secret")


@pytest.fixture(scope="module")
def _hostile_control_chars_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_hostile_control_chars")
    return _drive_logs_pty(tmp_path, ready_text="before", fixture="hostile_control_chars")


def _logs_content_row(regions: dict) -> int:
    logs = regions["logs"]
    return logs["y"] + 1  # LOGS' one content row at the real MIN_LINES floor


# ---------------------------------------------------------------------------
# (a) LOGS title + a non-secret real tail line visible in the band. Also
# pins the flash NEGATIVE case: a STATIC tail, captured well past its
# one-time arrival, is NOT bold (contrasts with the always-advancing
# positive case below).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_logs_title_and_real_tail_line_visible_and_not_flashing(_static_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    logs = regions["logs"]
    row = _logs_content_row(regions)
    grid = pyte_grid(_static_capture, FULL_ROWS, FULL_COLS)

    assert "LOGS" in grid[logs["y"]]
    assert "static-tail-line" in grid[row]

    screen = pyte_screen(_static_capture, FULL_ROWS, FULL_COLS)
    cell = screen.buffer[row][logs["x"] + 1]
    assert not cell.bold, (
        "a static (unchanging) tail line, captured well past its one-time "
        "arrival, must not still be flashing bold"
    )


# ---------------------------------------------------------------------------
# (b) Advancing lines -- a later capture shows a STRICTLY LARGER line
# number than an earlier one, proving the tail genuinely advances across
# real draws (not just at compose-time in isolation, already covered at
# Layer-A). Also pins the flash POSITIVE case: every draw against this
# always-growing fixture is a fresh arrival, so the newest row is bold at
# both captures.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_advancing_tail_shows_a_strictly_later_number_after_more_ticks(_advancing_captures):
    capture_early, capture_later = _advancing_captures
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)

    grid_early = pyte_grid(capture_early, FULL_ROWS, FULL_COLS)
    grid_later = pyte_grid(capture_later, FULL_ROWS, FULL_COLS)

    n_early = _extract_advancing_number(grid_early[row])
    n_later = _extract_advancing_number(grid_later[row])
    assert n_early is not None, f"expected an advancing-line-N marker, got {grid_early[row]!r}"
    assert n_later is not None, f"expected an advancing-line-N marker, got {grid_later[row]!r}"
    assert n_later > n_early, (
        f"expected the tail to have advanced further after more real ticks, "
        f"got early={n_early} later={n_later}"
    )


@_PTY_SKIP
def test_newest_row_stays_bold_while_the_tail_keeps_advancing(_advancing_captures):
    capture_early, capture_later = _advancing_captures
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    logs = regions["logs"]
    content_col = logs["x"] + 1

    for label, capture in (("early", capture_early), ("later", capture_later)):
        screen = pyte_screen(capture, FULL_ROWS, FULL_COLS)
        cell = screen.buffer[row][content_col]
        assert cell.bold, (
            f"expected the always-advancing newest row to render bold at the "
            f"{label} capture, got bold={cell.bold!r}"
        )


# ---------------------------------------------------------------------------
# (c) SECRET fixture: the pre-redacted marker renders in the band; a
# sentinel planted in an UNRELATED status field never reaches ANY drawn
# row of the frame -- the absence sweep is grid-wide, not just the LOGS
# band's own row (no panel renders status["prompt"]).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_secret_marker_present_and_sentinel_absent_from_logs_band(_secret_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    grid = pyte_grid(_secret_capture, FULL_ROWS, FULL_COLS)

    assert _SECRET_MARKER in grid[row], (
        f"expected the pre-redacted marker in the LOGS band row, got {grid[row]!r}"
    )
    offenders = [r for r in grid if _SECRET_SENTINEL in r]
    assert not offenders, (
        "a sentinel planted in an UNRELATED status field ('prompt') must never "
        f"leak into ANY drawn row of the frame, found in: {offenders!r}"
    )


# ---------------------------------------------------------------------------
# (d) Honest-empty / status_line fallback: no log_tail field at all -- the
# ensure-session status_line renders instead of a bare "(none yet)".
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_no_log_tail_field_falls_back_to_status_line(_no_daemon_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    grid = pyte_grid(_no_daemon_capture, FULL_ROWS, FULL_COLS)

    assert "session ready" in grid[row], (
        f"expected the ensure-session status_line fallback in the LOGS band, got {grid[row]!r}"
    )
    assert "(none yet)" not in grid[row]


# ---------------------------------------------------------------------------
# (e) Esc -> back / q -> quit unchanged -- the LOGS wiring adds no new key
# handling. Mirrors every sibling pty suite's own regression leg.
# ---------------------------------------------------------------------------


class _NullWin:
    def __init__(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols

    def getmaxyx(self):
        return (self._rows, self._cols)

    def erase(self):
        return None

    def addstr(self, *a, **k):
        return None

    def refresh(self):
        return None


def test_play_shell_screen_handle_key_unchanged_esc_and_q_only(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)

    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("Q")) == "quit"
    # `ord(" ")` (Space) dropped from this list -- WO-AUTOLOOP-RELAUNCH-COCKPIT
    # legitimately binds it to the pause intent; this pin is only about
    # THIS module's own wiring not adding new key handling.
    for key in (curses.KEY_UP, curses.KEY_DOWN, ord("1"), ord("d")):
        assert screen.handle_key(key) is None


# ---------------------------------------------------------------------------
# (f) Hostile control-char payload inside a tail line is neutralized by the
# shared draw choke point (cockpit.draw._safe_write), same guarantee
# already proven for status_line
# (tests/test_cockpit_frame_pty.py::test_embedded_newline_in_status_line_does_not_escape_box)
# -- chrome (the outer frame's own border) stays intact.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_embedded_newline_in_tail_line_does_not_escape_box(_hostile_control_chars_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    outer = regions["outer"]

    grid = pyte_grid(_hostile_control_chars_capture, FULL_ROWS, FULL_COLS)
    screen = pyte_screen(_hostile_control_chars_capture, FULL_ROWS, FULL_COLS)

    next_row = row + 1
    # The sanitized \n becomes a plain space -- content stays on ONE row and
    # never moves the terminal cursor, so nothing bleeds onto the next row,
    # let alone past the outer frame's own left border at column 0.
    assert "BREAKOUT" not in grid[next_row]
    assert screen.buffer[next_row][outer["x"]].data == "║"  # outer frame's own border, untouched

    logs = regions["logs"]
    left_x = logs["x"]
    right_x = logs["x"] + logs["w"] - 1
    assert screen.buffer[row][left_x].data == "│"
    assert screen.buffer[row][right_x].data == "│"


# ---------------------------------------------------------------------------
# Poll-guard: LOGS is a SEVENTH consumer of the same shared
# status_provider() snapshot -- still exactly one poll per draw() at the
# full tier, mirroring every sibling poll-guard test in this suite family.
# ---------------------------------------------------------------------------


def test_poll_guard_still_fires_exactly_once_with_logs_consuming_the_snapshot(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["logs"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _NullWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"connected": True, "idle_ms": 1, "log_tail": ["a", "b"]}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll with LOGS consuming the same "
        f"snapshot, got {len(calls)}"
    )


# ---------------------------------------------------------------------------
# Unit-level: flash-state tracking / status_line fallback / hostile
# now_fn -- no pty/curses needed, mirrors
# tests/test_cockpit_liveness_pty.py's own unit-level now_fn seam proofs.
# ---------------------------------------------------------------------------


class _RecordingWin(_NullWin):
    def __init__(self, rows: int, cols: int) -> None:
        super().__init__(rows, cols)
        self.calls: list[tuple[int, int, str, int]] = []

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))


def _make_screen(monkeypatch, *, now_fn=None):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile, now_fn=now_fn)
    return screen, win


def test_status_line_fallback_used_when_no_real_tail(monkeypatch):
    screen, win = _make_screen(monkeypatch)
    screen.status_line = "session ready — main_command"
    screen.status_provider = lambda: {"connected": True, "idle_ms": 1}  # no log_tail
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls, "expected an addstr call on the LOGS content row"
    assert "session ready" in row_calls[-1]
    assert "(none yet)" not in row_calls[-1]


def test_real_tail_supersedes_status_line_fallback(monkeypatch):
    screen, win = _make_screen(monkeypatch)
    screen.status_line = "session ready — main_command"
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["real tail line"],
    }
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "real tail line" in row_calls[-1]
    assert "session ready" not in row_calls[-1]


def test_flash_state_persists_across_unchanged_newest_then_resets_on_change(monkeypatch):
    clock = {"t": 0.0}
    screen, win = _make_screen(monkeypatch, now_fn=lambda: clock["t"])
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["only line"],
    }

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)

    # First draw at t=0.0 -- fresh arrival, must flash bold.
    screen.draw()
    row_calls = [(text, attr) for (y, _x, text, attr) in win.calls if y == row]
    assert row_calls
    assert row_calls[-1][1] & curses.A_BOLD

    # Second draw, same content, well past the flash duration -- must NOT
    # still be bold (the arrival timestamp is not reset by an unchanged
    # newest entry).
    win.calls.clear()
    clock["t"] = 5.0
    screen.draw()
    row_calls = [(text, attr) for (y, _x, text, attr) in win.calls if y == row]
    assert row_calls
    assert not (row_calls[-1][1] & curses.A_BOLD)

    # Third draw, a genuinely NEW newest entry arrives at t=5.0 -- must
    # flash again.
    win.calls.clear()
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["only line", "new line"],
    }
    screen.draw()
    row_calls = [(text, attr) for (y, _x, text, attr) in win.calls if y == row]
    assert row_calls
    assert "new line" in row_calls[-1][0]
    assert row_calls[-1][1] & curses.A_BOLD


def test_flash_state_resets_when_tail_reverts_to_honest_empty(monkeypatch):
    clock = {"t": 0.0}
    screen, win = _make_screen(monkeypatch, now_fn=lambda: clock["t"])

    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["real line"],
    }
    screen.draw()
    assert screen._logs_last_newest == "real line"
    assert screen._logs_newest_arrival_s == 0.0

    # Tail reverts to empty (e.g. daemon restart) -- tracking resets sanely,
    # never leaves a stale arrival timestamp pointing at vanished content.
    screen.status_provider = lambda: {"connected": True, "idle_ms": 1}
    clock["t"] = 1.0
    screen.draw()
    assert screen._logs_last_newest is None
    assert screen._logs_newest_arrival_s is None


def test_raising_now_fn_does_not_crash_draw_and_logs_still_renders(monkeypatch):
    """Mirrors tests/test_cockpit_liveness_pty.py's own raising-now_fn
    proof: a raising now_fn (a public __init__ kwarg) must not escape
    draw(), and the LOGS content must still render (real content, not a
    crash) -- the flash decision itself degrades to "not flashing" rather
    than taking the draw pass down with it."""
    def _raising_now_fn():
        raise RuntimeError("clock seam is broken")

    screen, win = _make_screen(monkeypatch, now_fn=_raising_now_fn)
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["still here"],
    }

    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "still here" in row_calls[-1]


def test_raising_status_provider_falls_back_to_honest_state(monkeypatch):
    screen, win = _make_screen(monkeypatch)

    def _raising_provider():
        raise RuntimeError("daemon socket exploded")

    screen.status_provider = _raising_provider
    screen.status_line = ""
    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "(none yet)" in row_calls[-1]
