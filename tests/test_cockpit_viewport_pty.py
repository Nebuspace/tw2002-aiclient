"""WO-P4-051, lane B -- GAME viewport shell, real-curses pty proof.

Lane A (``screens.py``/``test_cockpit_frame_pty.py``/``test_cockpit_layout.py``,
built concurrently and never touched here) removes ``_GAME_PLACEHOLDER`` --
the honest "(placeholder -- live game viewport wired in a later WO)" line
that has stood in for the GAME panel's own content since PWO-031/033. This
file proves the *drawn* result of that removal: the bordered/borderless
viewport shell itself (title, border-weight, corner glyphs, geometry) still
renders correctly, and every trace of the placeholder text is gone from the
frame -- at the full tier, the minimal (no side gutters) tier, and the
no-border tier, plus an Esc/q regression leg and an ASCII-twin parity leg.
Layer-A pure-geometry coverage stays in ``tests/test_cockpit_layout.py``
(lane A's); this file is Layer-B only, real curses + pyte replay
(``tests.pty_helpers``), assertions read pyte grid text and
``screen.buffer[r][c]`` cell attrs only -- never an ANSI-escape regex (house
pty law).

Ready-text marker: the GAME viewport's own interior is BLANK BY DESIGN once
the placeholder is gone (canon calls for zero invented content, and no real
game-frame content is wired yet) -- so a capture cannot condition-wait on
anything appearing *inside* the viewport itself. Every drive below instead
waits for the no-daemon ensure-session flow's own
``status_line = f"session ready — {classification}"`` (set by
``app.py::_run_play`` right after the stubbed ``ensure_session`` returns),
surfaced through the LOGS band's honest-empty fallback
(``tw2002_aiclient/cockpit/logsband.py``) -- real, LATE-arriving content
from a sibling panel, not an early structural marker like the bare "GAME"
title (which paints on the very first draw, before the ensure-session round
trip completes -- the WO-P3-038/039 lesson: never condition-wait on a
structural marker when a genuine content one is available). A short settle
after the marker appears lets that same draw pass's GAME-panel writes (or
lack thereof) fully land before capture.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process (no live daemon, no ``run/twd.sock`` touched either way);
``TW_RUN_DIR`` always points at an isolated per-test tmp directory so the
real (unstubbed) ``app._daemon_status_provider`` path can never reach the
project's own ``run/twd.sock`` -- same convention as every sibling
cockpit-panel pty suite (mirrors ``tests/test_cockpit_logsband_pty.py``'s
own ``_spawn``/``_drive_logs_pty``/``_settle``/``_teardown`` shape almost
verbatim, parameterized on terminal size instead of a status fixture).
"""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from tw2002_aiclient.cockpit.layout import GAME_H, GAME_W, frame_layout

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

# Three tiers exercising every border state ``frame_layout`` can hand the
# GAME viewport (visual-language.md "Responsive-fold ladder"):
#   FULL     -- >=154 inner cols -- bordered, both gutters present
#   MINIMAL  -- >=82  inner cols -- bordered, no side gutters
#   NO_BORDER-- >=60  inner cols -- border dropped, viewport full-bleed/clipped
# Matches every sibling cockpit-panel pty suite's own FULL constants; the
# minimal/no-border sizes are chosen from layout.py's own documented floors
# (MINIMAL_HEADER_MIN_COLS=82, MIN_COLS=60), comfortably inside each band
# without straddling a neighboring tier's floor.
FULL_ROWS, FULL_COLS = 40, 180
MINIMAL_ROWS, MINIMAL_COLS = 26, 100  # inner cols 98: >=82, <126 -> "minimal"
NO_BORDER_ROWS, NO_BORDER_COLS = 26, 70  # inner cols 68: >=60, <82 -> "no_border"

_DOUBLE_GLYPHS_UNICODE = ("╔", "╗", "╚", "╝")
_DOUBLE_GLYPHS_ASCII = ("+", "+", "+", "+")
_THIN_GLYPHS_UNICODE = ("╭", "╮", "╰", "╯")

_READY_TEXT = "session ready"

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock) --
# same shape as tests/test_cockpit_logsband_pty.py's own _BOOTSTRAP, minus
# the log-tail fixture machinery this file doesn't need (the marker comes
# from the honest-empty status_line fallback alone).
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
    return EnsureResult(ok=True, classification="unknown")  # no App-armed explore kick in chrome PTY


adapters.ensure_session = _fake_ensure

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining ``master_fd`` for ``seconds`` of wall time -- a single
    post-condition ``read()`` isn't reliable (``PlayShellScreen.draw()``'s one
    ``refresh()`` call still spans multiple OS-level pty read chunks for a
    full frame), same helper shape as every sibling cockpit-panel pty suite's
    own ``_settle``."""
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


def _spawn(
    tmp_path: Path, bootstrap_name: str, rows: int, cols: int, *, ascii_mode: bool
) -> tuple[subprocess.Popen, int]:
    bootstrap = tmp_path / bootstrap_name
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if ascii_mode:
        env["TW2002_ASCII"] = "1"
    else:
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


def _drive_viewport_pty(
    tmp_path: Path, rows: int, cols: int, *, ascii_mode: bool = False, timeout: float = 14.0
) -> bytes:
    """Spawn ``app._run`` in a ``rows``x``cols`` pty: Enter from the launcher
    once its chrome is up, capture the play-shell cockpit frame once
    ``_READY_TEXT`` ("session ready", the LOGS band's honest-empty fallback)
    is visible ANYWHERE on screen (settling briefly after that so the same
    draw pass's GAME-panel writes have fully landed), then quit.
    """
    proc, master_fd = _spawn(
        tmp_path, f"viewport_pty_bootstrap_{rows}x{cols}_{int(ascii_mode)}.py",
        rows, cols, ascii_mode=ascii_mode,
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

            grid = pyte_grid(captured, rows, cols)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, _READY_TEXT):
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
        f"pty viewport drive stalled in phase={phase!r} at {rows}x{cols} "
        f"ascii_mode={ascii_mode!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


def _assert_placeholder_absent(grid: list[str]) -> None:
    text = "\n".join(grid).lower()
    assert "placeholder" not in text, (
        f"expected the removed GAME placeholder text nowhere in the frame, "
        f"found it in:\n{text}"
    )


def _assert_bordered_interior_blank(grid: list[str], center: dict) -> None:
    """Every interior row inside a double-bordered ``center`` region is
    blank -- spaces only -- across its own inner width (``center['w'] - 2``,
    never a hardcoded column count)."""
    y, x, w, h = center["y"], center["x"], center["w"], center["h"]
    inner_y0, inner_x0 = y + 1, x + 1
    inner_w, inner_h = w - 2, h - 2
    for row in range(inner_y0, inner_y0 + inner_h):
        segment = grid[row][inner_x0 : inner_x0 + inner_w]
        assert segment == " " * inner_w, (
            f"expected center interior row {row} blank across {inner_w} cols, "
            f"got {segment!r}"
        )


def _assert_double_border_corners(screen, center: dict, glyphs: tuple[str, str, str, str]) -> None:
    tl_g, tr_g, bl_g, br_g = glyphs
    y, x, w, h = center["y"], center["x"], center["w"], center["h"]
    assert screen.buffer[y][x].data == tl_g
    assert screen.buffer[y][x + w - 1].data == tr_g
    assert screen.buffer[y + h - 1][x].data == bl_g
    assert screen.buffer[y + h - 1][x + w - 1].data == br_g


def _assert_region_fully_blank(grid: list[str], region: dict) -> None:
    """Every cell of ``region`` (its own full ``w``x``h`` footprint, no
    border inset) is blank -- used for the borderless ``no_border`` tier,
    where the GAME viewport owns no border row/col of its own to exclude."""
    y, x, w, h = region["y"], region["x"], region["w"], region["h"]
    for row in range(y, y + h):
        segment = grid[row][x : x + w]
        assert segment == " " * w, (
            f"expected no_border center region row {row} fully blank across "
            f"{w} cols, got {segment!r}"
        )


# ---------------------------------------------------------------------------
# Full tier (40x180, "full" mode): bordered viewport, GAME title, blank
# 80-col interior, double-line corners.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _full_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_full")
    return _drive_viewport_pty(tmp_path, FULL_ROWS, FULL_COLS)


@_PTY_SKIP
def test_full_tier_placeholder_absent_from_entire_grid(_full_capture):
    grid = pyte_grid(_full_capture, FULL_ROWS, FULL_COLS)
    _assert_placeholder_absent(grid)


@_PTY_SKIP
def test_full_tier_game_title_on_center_top_border_row(_full_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["mode"] == "full"
    center = regions["center"]
    assert center is not None and center["border"] is True
    grid = pyte_grid(_full_capture, FULL_ROWS, FULL_COLS)
    assert "GAME" in grid[center["y"]]


@_PTY_SKIP
def test_full_tier_center_interior_blank_across_full_80_col_width(_full_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    # Sanity-pin: at the full tier the bordered viewport's own inner width is
    # exactly layout.py's GAME_W (80) -- the canon-cited native content size
    # the bordered viewport wraps with zero inset (VIEWPORT_W - 2).
    assert center["w"] - 2 == GAME_W
    grid = pyte_grid(_full_capture, FULL_ROWS, FULL_COLS)
    _assert_bordered_interior_blank(grid, center)


@_PTY_SKIP
def test_full_tier_center_double_border_corners_present(_full_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    screen = pyte_screen(_full_capture, FULL_ROWS, FULL_COLS)
    _assert_double_border_corners(screen, center, _DOUBLE_GLYPHS_UNICODE)


# ---------------------------------------------------------------------------
# Minimal tier (26x100, "minimal" mode): bordered viewport still present
# (both side gutters shed), same GAME title/blank-interior/corner contract.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _minimal_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_minimal")
    return _drive_viewport_pty(tmp_path, MINIMAL_ROWS, MINIMAL_COLS)


@_PTY_SKIP
def test_minimal_tier_bordered_viewport_present_and_sane(_minimal_capture):
    regions = frame_layout(MINIMAL_ROWS, MINIMAL_COLS)
    assert regions["mode"] == "minimal"
    assert regions["left_gutter"] is None
    assert regions["right_gutter"] is None
    center = regions["center"]
    assert center is not None and center["border"] is True
    assert center["h"] <= GAME_H + 2  # never taller than the viewport's own H floor

    grid = pyte_grid(_minimal_capture, MINIMAL_ROWS, MINIMAL_COLS)
    screen = pyte_screen(_minimal_capture, MINIMAL_ROWS, MINIMAL_COLS)

    assert "GAME" in grid[center["y"]]
    _assert_bordered_interior_blank(grid, center)
    _assert_double_border_corners(screen, center, _DOUBLE_GLYPHS_UNICODE)


@_PTY_SKIP
def test_minimal_tier_placeholder_absent(_minimal_capture):
    grid = pyte_grid(_minimal_capture, MINIMAL_ROWS, MINIMAL_COLS)
    _assert_placeholder_absent(grid)


# ---------------------------------------------------------------------------
# No-border tier (26x70, "no_border" mode): border dropped entirely, the
# viewport slot is full-bleed/clipped and left wholly blank -- no box, no
# title, no placeholder. The row-1 strip owns its OWN row (outside this
# region entirely -- rest_y = oy + STRIP_H puts center strictly below it),
# so nothing legitimate ever lands inside center at this tier either; the
# whole region is provably blank, not just its would-be interior.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _no_border_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_no_border")
    return _drive_viewport_pty(tmp_path, NO_BORDER_ROWS, NO_BORDER_COLS)


@_PTY_SKIP
def test_no_border_tier_draws_without_crash_placeholder_absent(_no_border_capture):
    # The drive helper itself already proves "no crash" -- phase=="done" was
    # asserted inside _drive_viewport_pty before this fixture could return;
    # a curses/draw exception would have stalled the drive in "wait_frame"
    # and failed there with the captured grid dumped for diagnosis.
    regions = frame_layout(NO_BORDER_ROWS, NO_BORDER_COLS)
    assert regions["mode"] == "no_border"
    center = regions["center"]
    assert center is not None and center["border"] is False

    grid = pyte_grid(_no_border_capture, NO_BORDER_ROWS, NO_BORDER_COLS)
    _assert_placeholder_absent(grid)
    assert "GAME" not in "\n".join(grid), "no_border tier draws no box, so no GAME title either"


@_PTY_SKIP
def test_no_border_tier_center_region_has_no_stray_text(_no_border_capture):
    regions = frame_layout(NO_BORDER_ROWS, NO_BORDER_COLS)
    strip, center = regions["strip"], regions["center"]
    # Geometry sanity: the strip band and the center region never overlap at
    # this tier (center starts strictly below row 1) -- so "whatever the
    # header/strip legitimately put there" is provably nothing, and the
    # assert below can honestly demand the WHOLE center footprint be blank.
    assert center["y"] > strip["y"] + strip["h"] - 1

    grid = pyte_grid(_no_border_capture, NO_BORDER_ROWS, NO_BORDER_COLS)
    _assert_region_fully_blank(grid, center)


# ---------------------------------------------------------------------------
# Esc -> back / q -> quit regression: the GAME-panel content change adds no
# new key handling. Unit-level fake window, mirrors every sibling pty
# suite's own regression leg (e.g.
# tests/test_cockpit_logsband_pty.py::test_play_shell_screen_handle_key_unchanged_esc_and_q_only).
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
    import curses

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
# ASCII-twin parity (TW2002_ASCII=1) at the full tier: GAME box renders with
# ASCII corner/edge twins, no unicode box-drawing glyph leaks through,
# placeholder still absent. Mirrors
# tests/test_cockpit_frame_pty.py::test_ascii_twin_closure_glyphs_no_unicode_leak.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_ascii_twin_full_tier_game_box_ascii_corners_no_unicode_leak(tmp_path):
    captured = _drive_viewport_pty(tmp_path, FULL_ROWS, FULL_COLS, ascii_mode=True)
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert center["border"] is True

    grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)
    screen = pyte_screen(captured, FULL_ROWS, FULL_COLS)
    text = "\n".join(grid)

    assert "GAME" in grid[center["y"]]
    _assert_double_border_corners(screen, center, _DOUBLE_GLYPHS_ASCII)
    _assert_placeholder_absent(grid)

    for glyph in _DOUBLE_GLYPHS_UNICODE + _THIN_GLYPHS_UNICODE:
        assert glyph not in text
