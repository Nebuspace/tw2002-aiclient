"""WO-P3-030-033 — Trainer-cockpit frame chrome (PWO-031/033), Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
chrome, not just the pure geometry already covered at Layer-A
(``tests/test_cockpit_layout.py``, ``tests/test_cockpit_strip.py``): the
outer frame's double-line corner glyphs and cyan+bold color at a full-tier
size, the four panel titles, the row-1 strip text (rendered as DATA, not
chrome -- not cyan), an ASCII-twin run, a narrow run that sheds the left
gutter, a tall run that leaves the reserved sub-panel band unpainted, the
too_small refusal, and the two untrusted-content hazards `draw.py`'s
``_safe_write`` neutralizes: a CJK-heavy free-text value that would overflow
a panel's cell budget if clipped by Python-character count instead of
display width, and an embedded control character (``\n``) that would
otherwise move the real terminal cursor and escape the writing box entirely.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process; ``TW_RUN_DIR`` always points at an isolated per-test tmp
directory so the real (unstubbed) ``WatchFeed`` / status-provider path
can never reach the project's own ``run/twd.sock`` (WO-TEST-COCKPIT-
FRAME-PTY-ISOLATE — ambient daemon must not paint the GAME viewport).
Assertions read pyte grid text and ``screen.buffer[r][c]`` cell attrs
only -- never an ANSI-escape regex (PREP §2 hard constraint). One test
(title-clip) is a pure logic unit test against a minimal fake window
and needs no pty.
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


import curses

from tw2002_aiclient.cockpit import draw as cockpit_draw
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
HOST = "demo-a.example"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

_DOUBLE_GLYPHS_UNICODE = ("╔", "╗", "╚", "╝")
_THIN_GLYPHS_UNICODE = ("╭", "╮", "╰", "╯")

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as tests/test_play_chrome_nav.py's _BOOTSTRAP. The ensure stub's
# classification is env-overridable so callers can inject adversarial
# free-text content that ends up in PlayShellScreen's real status_line via
# the real app._run_play flow (status_line = f"session ready — {classification}"),
# rather than poking PlayShellScreen directly.
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

_CLASSIFICATION = os.environ.get("TW2002_TEST_CLASSIFICATION", "main_command")


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification=_CLASSIFICATION)


adapters.ensure_session = _fake_ensure

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive_cockpit_frame_pty(
    tmp_path: Path,
    rows: int,
    cols: int,
    *,
    ascii_mode: bool = False,
    classification: str | None = None,
    timeout: float = 12.0,
) -> bytes:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols``: Enter from the
    launcher once its chrome is up, capture the play-shell cockpit frame (or
    the ``too_small`` refusal), then clean-quit with ``q``.

    ``classification`` (when given) becomes the stubbed ensure's
    classification, which lands verbatim in ``PlayShellScreen.status_line``
    -- lets a test inject adversarial free-text (CJK/control chars) through
    the real app flow instead of poking the screen object directly.

    Mirrors ``tests/test_play_chrome_nav.py::_drive_launcher_play_esc_in_pty``'s
    poll-and-decide loop (pyte grid text drives phase transitions, never a
    raw-byte marker match).
    """
    bootstrap = tmp_path / f"cockpit_frame_bootstrap_{rows}x{cols}_{int(ascii_mode)}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    # Same as test_cockpit_viewport_pty / tones / logsband: ensure-stub alone
    # is not enough — WatchFeed still opens resolve_run_dir()/twd.sock.
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if ascii_mode:
        env["TW2002_ASCII"] = "1"
    else:
        env.pop("TW2002_ASCII", None)
    if classification is not None:
        env["TW2002_TEST_CLASSIFICATION"] = classification
    else:
        env.pop("TW2002_TEST_CLASSIFICATION", None)
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
            text = "\n".join(grid)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if "Terminal too small" in text or find_text(grid, "PLAY SHELL"):
                    os.write(master_fd, b"q")
                    phase = "done"
                    break
        if phase != "done":
            try:
                os.write(master_fd, b"q")
            except OSError:
                pass
    finally:
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

    assert phase == "done", (
        f"pty cockpit-frame drive stalled in phase={phase!r} at {rows}x{cols}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


# ---------------------------------------------------------------------------
# Full tier (40x160, "full" mode): double-line outer frame, cyan+bold
# corners, all four titled panels, row-1 strip text.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _full_tier_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("cockpit_full")
    return _drive_cockpit_frame_pty(tmp_path, 40, 160)


@_PTY_SKIP
def test_full_tier_outer_frame_double_line_corners_cyan_bold(_full_tier_capture):
    regions = frame_layout(40, 160)
    assert regions["mode"] == "full"
    outer = regions["outer"]
    screen = pyte_screen(_full_tier_capture, 40, 160)

    top_y, bottom_y = outer["y"], outer["y"] + outer["h"] - 1
    left_x, right_x = outer["x"], outer["x"] + outer["w"] - 1
    tl, tr = screen.buffer[top_y][left_x], screen.buffer[top_y][right_x]
    bl, br = screen.buffer[bottom_y][left_x], screen.buffer[bottom_y][right_x]

    assert (tl.data, tr.data, bl.data, br.data) == _DOUBLE_GLYPHS_UNICODE
    for cell in (tl, tr, bl, br):
        assert cell.fg == "cyan"
        assert cell.bold


@_PTY_SKIP
def test_full_tier_panel_titles_at_expected_rows(_full_tier_capture):
    regions = frame_layout(40, 160)
    grid = pyte_grid(_full_tier_capture, 40, 160)

    left, center, right, logs = (
        regions["left_gutter"],
        regions["center"],
        regions["right_gutter"],
        regions["logs"],
    )
    assert left is not None and right is not None and center is not None and logs is not None

    assert "FOCUS" in grid[left["y"]]
    assert "GAME" in grid[center["y"]]
    assert "HUD" in grid[right["y"]]
    assert "LOGS" in grid[logs["y"]]
    # PLAY SHELL rides the outer frame's own top-border row.
    assert "PLAY SHELL" in grid[regions["outer"]["y"]]


@_PTY_SKIP
def test_full_tier_strip_shows_host_and_handle_on_row_1(_full_tier_capture):
    regions = frame_layout(40, 160)
    strip_row = regions["strip"]["y"]
    grid = pyte_grid(_full_tier_capture, 40, 160)

    assert HOST in grid[strip_row]
    assert HANDLE in grid[strip_row]


@_PTY_SKIP
def test_full_tier_strip_row_is_data_not_chrome_colored(_full_tier_capture):
    """Pixel canon ruling: strip content is profile identity DATA, never
    chrome -- must not carry the cyan chrome tint every border/title uses."""
    regions = frame_layout(40, 160)
    screen = pyte_screen(_full_tier_capture, 40, 160)

    strip = regions["strip"]
    strip_cell = screen.buffer[strip["y"]][strip["x"]]  # first char of the composed strip text
    assert strip_cell.fg != "cyan"

    outer = regions["outer"]
    border_cell = screen.buffer[outer["y"]][outer["x"]]
    assert border_cell.fg == "cyan"  # the border itself is still chrome-tinted


@_PTY_SKIP
def test_full_tier_center_viewport_is_double_line_and_empty_panels_honest(_full_tier_capture):
    """PWO-051: the GAME viewport's own honesty is a BLANK grid -- no
    placeholder text, no fake content, just the double-line border around
    empty interior cells (the live pyte/settle paint is PWO-052). FOCUS
    states its own emptiness a different way -- an explicit em-dash row --
    since it's a data panel with a real honest-empty composer, unlike GAME
    which has no content composer at all yet."""
    regions = frame_layout(40, 160)
    screen = pyte_screen(_full_tier_capture, 40, 160)
    grid = list(screen.display)

    center = regions["center"]
    assert center["border"] is True
    top_y, left_x = center["y"], center["x"]
    assert screen.buffer[top_y][left_x].data == "╔"

    # The placeholder string is gone grid-wide (PWO-051 kill).
    assert "placeholder" not in "\n".join(grid).lower()

    # GAME's own interior is honestly blank -- zero cells painted, matching
    # the "empty 80x25" Accept criterion (PREP §PWO-051), not merely "no
    # placeholder word present" (which an unrelated stray glyph could
    # satisfy too).
    interior_top = center["y"] + 1
    interior_bottom = center["y"] + center["h"] - 1  # exclusive of the bottom border row
    interior_left = center["x"] + 1
    interior_right = center["x"] + center["w"] - 1  # exclusive of the right border column
    for row in range(interior_top, interior_bottom):
        assert grid[row][interior_left:interior_right].strip() == "", (
            f"GAME interior row {row} carries non-blank content"
        )

    left = regions["left_gutter"]
    assert "—" in grid[left["y"] + 1]  # FOCUS empty-state row (no focus payload wired yet)


# ---------------------------------------------------------------------------
# ASCII twin (TW2002_ASCII=1): same size, closure glyphs only, no stray
# unicode box-drawing leaks through.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_ascii_twin_closure_glyphs_no_unicode_leak(tmp_path):
    captured = _drive_cockpit_frame_pty(tmp_path, 40, 160, ascii_mode=True)
    regions = frame_layout(40, 160)
    screen = pyte_screen(captured, 40, 160)
    grid = list(screen.display)
    text = "\n".join(grid)

    outer = regions["outer"]
    top_y, bottom_y = outer["y"], outer["y"] + outer["h"] - 1
    left_x, right_x = outer["x"], outer["x"] + outer["w"] - 1
    corners = (
        screen.buffer[top_y][left_x].data,
        screen.buffer[top_y][right_x].data,
        screen.buffer[bottom_y][left_x].data,
        screen.buffer[bottom_y][right_x].data,
    )
    assert corners == ("+", "+", "+", "+")
    assert "PLAY SHELL" in text
    assert "FOCUS" in text and "GAME" in text and "HUD" in text and "LOGS" in text

    for glyph in _DOUBLE_GLYPHS_UNICODE + _THIN_GLYPHS_UNICODE:
        assert glyph not in text


# ---------------------------------------------------------------------------
# Narrow run (raw cols < 120): left gutter shed, nothing drawn past the
# window's true right edge.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_narrow_run_left_gutter_absent_frame_flush_to_right_edge(tmp_path):
    rows, cols = 40, 100  # raw < 120 -> inner cols 98 -> "minimal" tier
    captured = _drive_cockpit_frame_pty(tmp_path, rows, cols)
    regions = frame_layout(rows, cols)
    assert regions["mode"] == "minimal"
    assert regions["left_gutter"] is None
    assert regions["right_gutter"] is None

    screen = pyte_screen(captured, rows, cols)
    grid = list(screen.display)
    text = "\n".join(grid)

    assert "PLAY SHELL" in text
    assert "FOCUS" not in text  # left gutter shed at this tier
    assert "HUD" not in text  # right gutter shed at this tier too (minimal)

    outer = regions["outer"]
    right_x = outer["x"] + outer["w"] - 1
    assert right_x == cols - 1  # the frame's right edge IS the window's last column
    assert screen.buffer[outer["y"]][right_x].data == "╗"
    assert screen.buffer[outer["y"] + outer["h"] - 1][right_x].data == "╝"
    # Every displayed row is exactly `cols` wide by construction (pyte); the
    # frame's own right edge sits on the true last column, never beyond it.
    for row_text in grid:
        assert len(row_text) == cols


# ---------------------------------------------------------------------------
# Untrusted content hazards (Mack): a free-text status_line can carry
# anything -- a CJK-heavy value that overflows a Python-character-count clip,
# or a raw control char (embedded \n) that would move the real terminal
# cursor and escape the writing box. Both are injected through the real
# app._run_play flow (status_line = f"session ready — {classification}"),
# not by poking PlayShellScreen directly.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_cjk_heavy_status_line_preserves_logs_right_border(tmp_path):
    rows, cols = 40, 160
    # Wide (2-cell) glyphs, repeated well past the LOGS interior width --
    # a raw Python-character-count clip would still let this through and
    # overflow the box's own right border on a real terminal.
    classification = "国" * 100
    captured = _drive_cockpit_frame_pty(tmp_path, rows, cols, classification=classification)
    regions = frame_layout(rows, cols)
    logs = regions["logs"]
    screen = pyte_screen(captured, rows, cols)

    content_row = logs["y"] + 1  # status_line is the LOGS box's one content line
    left_x = logs["x"]
    right_x = logs["x"] + logs["w"] - 1
    assert screen.buffer[content_row][left_x].data == "│"
    assert screen.buffer[content_row][right_x].data == "│"


@_PTY_SKIP
def test_embedded_newline_in_status_line_does_not_escape_box(tmp_path):
    rows, cols = 40, 160
    classification = "before\nBREAKOUT-AFTER-NEWLINE"
    captured = _drive_cockpit_frame_pty(tmp_path, rows, cols, classification=classification)
    regions = frame_layout(rows, cols)
    logs = regions["logs"]
    outer = regions["outer"]
    screen = pyte_screen(captured, rows, cols)
    grid = pyte_grid(captured, rows, cols)

    content_row = logs["y"] + 1
    next_row = content_row + 1
    # The sanitized \n becomes a plain space -- content stays on ONE row and
    # never moves the terminal cursor, so nothing bleeds onto the next row,
    # let alone past the outer frame's own left border at column 0.
    assert "BREAKOUT" not in grid[next_row]
    assert screen.buffer[next_row][outer["x"]].data == "║"  # outer frame's own border, untouched


# ---------------------------------------------------------------------------
# Tall terminal: the reserved gap between the gutters/center bottom and the
# LOGS top (out of PWO-031/033 scope -- later-WO sub-panels) must stay
# unpainted -- no border, no box, no filler text (Mack geometry-attack note).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_tall_terminal_leaves_reserved_band_unpainted(tmp_path):
    rows, cols = 200, 160
    captured = _drive_cockpit_frame_pty(tmp_path, rows, cols)
    regions = frame_layout(rows, cols)
    assert regions["mode"] == "full"

    left, logs = regions["left_gutter"], regions["logs"]
    gap_top = left["y"] + left["h"]  # first row after gutters/center bottom
    gap_bottom = logs["y"]  # first row of LOGS -- gap is [gap_top, gap_bottom)
    assert gap_bottom > gap_top, "fixture no longer produces a reserved band -- update the size"

    screen = pyte_screen(captured, rows, cols)
    outer = regions["outer"]
    interior_cols = range(outer["x"] + 1, outer["x"] + outer["w"] - 1)  # excludes the outer's own side border
    box_glyphs = set(_DOUBLE_GLYPHS_UNICODE + _THIN_GLYPHS_UNICODE) | {"+", "=", "-", "|"}

    leaked = [
        (row, col)
        for row in range(gap_top, gap_bottom)
        for col in interior_cols
        if screen.buffer[row][col].data in box_glyphs
    ]
    assert leaked == [], f"box-drawing glyph(s) painted into the reserved band: {leaked[:10]}"


# ---------------------------------------------------------------------------
# Below the fold floor: refuse, render nothing else.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_too_small_refuses_with_message_and_no_chrome(tmp_path):
    rows, cols = 18, 55  # both below MIN_LINES=20 / MIN_COLS=60
    captured = _drive_cockpit_frame_pty(tmp_path, rows, cols)
    regions = frame_layout(rows, cols)
    assert regions["mode"] == "too_small"

    grid = pyte_grid(captured, rows, cols)
    text = "\n".join(grid)

    assert "Terminal too small" in text
    for glyph in _DOUBLE_GLYPHS_UNICODE + _THIN_GLYPHS_UNICODE:
        assert glyph not in text
    assert "FOCUS" not in text
    assert "GAME" not in text
    assert "HUD" not in text
    assert "LOGS" not in text


# ---------------------------------------------------------------------------
# Pure logic unit test (no pty/curses needed): draw_box's own title clip.
# ---------------------------------------------------------------------------


class _GridWin:
    """Minimal fake curses window for testing ``draw_box``/``draw_lines*``
    in isolation: records ``addstr`` writes into a 2D character grid, plus
    the ``attr`` each write carried (needed by the ``draw_lines_attrs``
    tests below; unused by the pre-existing title-clip test). ``draw.py``'s
    ``_safe_write`` only ever calls ``getmaxyx``/``addstr`` on its window
    argument, so this is a complete-enough double without real curses or a
    pty (mirrors ``tests/test_play_chrome_nav.py::_RecordingStdscr``'s
    addstr-only surface)."""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows, self.cols = rows, cols
        self.grid = [[" "] * cols for _ in range(rows)]
        self.attrs = [[0] * cols for _ in range(rows)]

    def getmaxyx(self) -> tuple[int, int]:
        return self.rows, self.cols

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        for i, ch in enumerate(text):
            col = x + i
            if 0 <= col < self.cols:
                self.grid[y][col] = ch
                self.attrs[y][col] = attr

    def row_text(self, y: int) -> str:
        return "".join(self.grid[y])

    def attr_at(self, y: int, x: int) -> int:
        return self.attrs[y][x]


def test_draw_box_overlong_title_does_not_clobber_top_right_corner():
    """A title far longer than the box's own interior must not bleed past
    this box's own right border -- _safe_write's window-edge clip alone
    isn't enough for a narrow interior box far from the window's true edge."""
    win = _GridWin(10, 40)
    region = {"y": 0, "x": 0, "w": 20, "h": 5}
    cockpit_draw.draw_box(win, region, weight="thin", attr=0, title="X" * 100, uok=True)

    row0 = win.row_text(0)
    assert row0[region["x"]] == "╭"  # top-left corner intact
    assert row0[region["x"] + region["w"] - 1] == "╮"  # top-right corner intact


# ---------------------------------------------------------------------------
# Pure logic unit tests: draw_lines_attrs (PWO-037 HUD-review REVISE) -- the
# per-line-attr sibling of draw_lines, added so a panel can dim ONE line
# in a box without bypassing draw.py's own sanitize/cell-clip choke point.
# ---------------------------------------------------------------------------


def test_draw_lines_attrs_applies_a_distinct_attr_per_line():
    """draw_lines_attrs's whole reason to exist: two lines in the SAME box
    render with two DIFFERENT curses attrs -- draw_lines's single flat attr
    cannot express this (HUD's stale-value-row dimming, PWO-037)."""
    win = _GridWin(10, 40)
    region = {"y": 0, "x": 0, "w": 20, "h": 5}
    cockpit_draw.draw_lines_attrs(
        win, region, [("LABEL", curses.A_NORMAL), ("12,345 stale", curses.A_DIM)]
    )

    inner_y, inner_x = region["y"] + 1, region["x"] + 1
    assert win.attr_at(inner_y, inner_x) == curses.A_NORMAL
    assert win.attr_at(inner_y + 1, inner_x) == curses.A_DIM


def test_draw_lines_attrs_clips_wide_glyphs_to_interior_cell_width():
    """A CJK/fullwidth line (2 cells per glyph) must clip by DISPLAY WIDTH,
    not Python-character count, or it bleeds past the box's own right
    border -- the pure-unit equivalent of
    ``tests/test_cockpit_frame_pty.py::test_cjk_heavy_status_line_preserves_logs_right_border``,
    proven directly at the ``draw_lines_attrs`` call this time."""
    win = _GridWin(10, 20)
    region = {"y": 0, "x": 0, "w": 12, "h": 4}  # interior w = 10 cells
    cockpit_draw.draw_box(win, region, weight="thin", attr=0, uok=True)
    cockpit_draw.draw_lines_attrs(win, region, [("国" * 20, curses.A_NORMAL)])

    row = win.row_text(1)
    assert row[region["x"] + region["w"] - 1] == "│", (
        "wide-glyph line bled past the box's own right border"
    )


def test_draw_lines_attrs_sanitizes_embedded_control_char():
    """An embedded control character (\\n) must be neutralized to a plain
    space by ``_safe_write``'s ``_sanitize_controls`` step. This fake window
    is dumb (it never interprets ``\\n`` as a cursor move the way a real
    terminal would), so the assertion is the literal character written at
    that cell rather than row-bleed -- the LIVE-terminal row-bleed hazard
    itself is proven by
    ``tests/test_cockpit_frame_pty.py::test_embedded_newline_in_status_line_does_not_escape_box``."""
    win = _GridWin(10, 40)
    region = {"y": 0, "x": 0, "w": 20, "h": 5}
    cockpit_draw.draw_lines_attrs(win, region, [("ab\ncd", curses.A_NORMAL)])

    inner_y, inner_x = region["y"] + 1, region["x"] + 1
    written = "".join(win.grid[inner_y][inner_x : inner_x + 5])
    assert written == "ab cd", (
        f"expected the embedded control char neutralized to a space, got {written!r}"
    )
