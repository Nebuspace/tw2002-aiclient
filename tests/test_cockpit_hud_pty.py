"""WO-P3-037 wire -- HUD freshness markers, Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn* HUD
box the ``screens.py``/``app.py`` wiring produces: the five fixed-order
labels (CREDITS/SECTOR/TURNS/CARGO/PROFIT) are visible top-to-bottom at both
the full tier and the narrowed ``right_gutter`` fold tier, a cold status (no
``"hud"`` key -- today's real daemon shape) renders every value cell as the
composer's own sticky ``"-"``, and a stubbed daemon status with a fresh and
a stale field renders the field's value plus its freshness stamp text.
Layer-A coverage for the composer itself (``compose_hud_cells``) lives in
``tests/test_cockpit_hud.py`` (the sibling composer WO); this file only
proves the ``PlayShellScreen``/``app.py`` wiring around it -- mirrors
``tests/test_cockpit_decisions_pty.py``'s split for DECISIONS.

Pyte does **not** model SGR-2 faint/dim (no ``.dim``/``.faint`` attribute on
its ``Char`` cells) -- a stale value row's ``curses.A_DIM`` attr cannot be
asserted through a pty/pyte replay. That mapping is instead proven with a
fake-stdscr attr-capture unit test at the draw call
(``test_hud_stale_value_rows_dim_label_rows_stay_normal``), which asserts
the exact ``attr`` argument ``PlayShellScreen.draw()`` passes for a stale
vs. a fresh/label row. This substitution is pre-authorized and disclosed
per the WO-P3-037 dispatch.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned process
(same convention as ``tests/test_cockpit_decisions_pty.py``), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory -- the
real ``status_provider`` (``app._daemon_status_provider``) is free to run
unstubbed against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) for the no-provider
scenario, and the fresh/stale scenarios additionally monkeypatch
``tw2002_aiclient.session.cli.send_request`` inside the bootstrap -- never
``run/twd.sock`` either way.
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

import curses

from tw2002_aiclient.cockpit.layout import frame_layout

from .pty_helpers import find_text, pty_curses_supported, pyte_grid, pyte_screen, set_winsize

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Full tier (both gutters at full width) and the narrowed right_gutter fold
# tier (left gutter narrowed, right gutter/HUD width unaffected --
# HUD_GUTTER_W is a fixed 36 across every has_right_gutter tier) -- the two
# sizes the dispatch calls out ("pty 40×160 and 40×142"), same as
# tests/test_cockpit_decisions_pty.py's FULL/NARROW constants.
FULL_ROWS, FULL_COLS = 40, 160
NARROW_ROWS, NARROW_COLS = 40, 142

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as tests/test_cockpit_decisions_pty.py's _BOOTSTRAP. One opt-in
# HUD status fixture stubs session_cli.send_request's "status" verb with a
# fresh field set plus one aged-past-FRESHNESS_STALE_S PROFIT field.
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

_HUD_FIXTURE = os.environ.get("TW2002_TEST_HUD_FIXTURE", "")
if _HUD_FIXTURE:
    from tw2002_aiclient.session import cli as session_cli

    _PROFIT_AGE = 25.0 if _HUD_FIXTURE == "stale" else 3.0
    # "cjk"/"escape" fixtures inject hostile content into CREDITS' string
    # value (a str payload renders verbatim through compose_hud_cells --
    # see hud.py's own "value formatting" docstring section) -- proves the
    # draw-layer's own sanitize/cell-clip choke point neutralizes it,
    # never the composer (which only clips by code-point count, not cells
    # or control chars -- hud.py's own "curses draw layer is the real
    # cell-width backstop" note).
    _CREDITS_VALUE = 54321
    if _HUD_FIXTURE == "cjk":
        _CREDITS_VALUE = "国" * 40  # far more than the HUD box's cell budget
    elif _HUD_FIXTURE == "escape":
        _CREDITS_VALUE = "\x1b[2Jinjected"  # a raw erase-display control sequence

    def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        if verb == "status":
            return {{
                "ok": True,
                "hud": {{
                    "credits": {{"value": _CREDITS_VALUE, "age_s": 3.0}},
                    "sector": {{"value": 1234, "age_s": 3.0}},
                    "turns": {{"value": 42, "age_s": 3.0}},
                    "cargo": {{"value": 3, "age_s": 3.0}},
                    "profit": {{"value": 500, "age_s": _PROFIT_AGE}},
                }},
            }}
        return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive_hud_pty(
    tmp_path: Path,
    rows: int,
    cols: int,
    *,
    hud_fixture: str | None = None,
    timeout: float = 12.0,
) -> bytes:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols``: Enter from the
    launcher once its chrome is up, capture the play-shell cockpit frame
    once HUD is visible (letting at least one ~1 Hz refresh tick land),
    then quit. Mirrors
    ``tests/test_cockpit_decisions_pty.py::_drive_decisions_pty``'s
    poll-and-decide loop.

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    so the real (unstubbed) status_provider path can never reach the
    project's own ``run/twd.sock`` regardless of which fixture is active.
    """
    bootstrap = tmp_path / f"hud_pty_bootstrap_{rows}x{cols}_{hud_fixture or 'none'}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if hud_fixture:
        env["TW2002_TEST_HUD_FIXTURE"] = hud_fixture
    else:
        env.pop("TW2002_TEST_HUD_FIXTURE", None)
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

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, "HUD"):
                    # Let at least one ~1 Hz refresh tick land before acting
                    # (proves the timeout-driven redraw doesn't crash/stall).
                    time.sleep(1.3)
                    ready, _, _ = select.select([master_fd], [], [], 0.2)
                    if master_fd in ready:
                        try:
                            chunk = os.read(master_fd, 65536)
                            captured += chunk
                        except OSError:
                            pass
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
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty HUD drive stalled in phase={phase!r} at {rows}x{cols}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


@pytest.fixture(scope="module")
def _full_tier_no_provider_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hud_full_no_provider")
    return _drive_hud_pty(tmp_path, FULL_ROWS, FULL_COLS)


@pytest.fixture(scope="module")
def _narrow_tier_no_provider_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hud_narrow_no_provider")
    return _drive_hud_pty(tmp_path, NARROW_ROWS, NARROW_COLS)


@pytest.fixture(scope="module")
def _full_tier_fresh_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hud_full_fresh")
    return _drive_hud_pty(tmp_path, FULL_ROWS, FULL_COLS, hud_fixture="fresh")


@pytest.fixture(scope="module")
def _full_tier_stale_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hud_full_stale")
    return _drive_hud_pty(tmp_path, FULL_ROWS, FULL_COLS, hud_fixture="stale")


# ---------------------------------------------------------------------------
# The five fixed-order labels, top-to-bottom, at both fold tiers.
# ---------------------------------------------------------------------------

_LABELS = ("CREDITS", "SECTOR", "TURNS", "CARGO", "PROFIT")


@_PTY_SKIP
def test_full_tier_hud_labels_visible_in_order(_full_tier_no_provider_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["mode"] == "full"
    hud = regions["right_gutter"]
    assert hud is not None
    grid = pyte_grid(_full_tier_no_provider_capture, FULL_ROWS, FULL_COLS)
    hud_rows = grid[hud["y"] : hud["y"] + hud["h"]]

    positions = []
    for label in _LABELS:
        pos = find_text(hud_rows, label)
        assert pos is not None, f"{label} not found in HUD box"
        positions.append(pos[0])
    assert positions == sorted(positions), f"HUD labels out of order: {positions}"


@_PTY_SKIP
def test_narrow_tier_hud_labels_visible_in_order(_narrow_tier_no_provider_capture):
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    # >=138 inner cols still carries the right gutter (HUD/DECISIONS) at its
    # full HUD_GUTTER_W -- only the LEFT gutter narrows at this tier.
    assert regions["mode"] == "right_gutter"
    hud = regions["right_gutter"]
    assert hud is not None
    grid = pyte_grid(_narrow_tier_no_provider_capture, NARROW_ROWS, NARROW_COLS)
    hud_rows = grid[hud["y"] : hud["y"] + hud["h"]]

    positions = []
    for label in _LABELS:
        pos = find_text(hud_rows, label)
        assert pos is not None, f"{label} not found in HUD box"
        positions.append(pos[0])
    assert positions == sorted(positions), f"HUD labels out of order: {positions}"


# ---------------------------------------------------------------------------
# No "hud" status key (real transport, empty isolated run dir; also the
# shape of today's real daemon, which carries no "hud" key yet) -> the
# composer's sticky "-" cold state on every value row, never blank.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_no_provider_hud_shows_honest_all_dash_cold_state(_full_tier_no_provider_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    hud = regions["right_gutter"]
    assert hud is not None
    grid = pyte_grid(_full_tier_no_provider_capture, FULL_ROWS, FULL_COLS)

    content_left = hud["x"] + 1
    content_right = hud["x"] + hud["w"] - 1  # exclusive -- box's own right border
    # Value rows sit at interior offsets 1,3,5,7,9 (label row then value row
    # per field, per compose_hud_cells' 2-row stride) -- interior row 0 is
    # hud["y"] + 1.
    for field_index, offset in enumerate((1, 3, 5, 7, 9)):
        row = grid[hud["y"] + 1 + offset][content_left:content_right].strip()
        assert row == "-", (
            f"expected sticky cold '-' at HUD value row {field_index} "
            f"({_LABELS[field_index]}), got {row!r}"
        )


# ---------------------------------------------------------------------------
# Stubbed provider: a fresh field shows its value + freshness stamp; a
# stale field (age_s >= FRESHNESS_STALE_S) still renders its value text
# (dim-attr mapping is a separate unit test -- see module docstring).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_fresh_fixture_shows_value_and_freshness_stamp(
    _full_tier_fresh_fixture_capture,
):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    hud = regions["right_gutter"]
    assert hud is not None
    grid = pyte_grid(_full_tier_fresh_fixture_capture, FULL_ROWS, FULL_COLS)
    hud_text = "\n".join(grid[hud["y"] : hud["y"] + hud["h"]])
    normalized = hud_text.replace(",", "")

    assert "54321" in normalized, f"expected fresh CREDITS value in HUD box, got:\n{hud_text}"
    assert "ago" in hud_text or "now" in hud_text, (
        f"expected a freshness stamp ('… ago' / 'now') in HUD box, got:\n{hud_text}"
    )


@_PTY_SKIP
def test_full_tier_stale_fixture_value_still_renders(_full_tier_stale_fixture_capture):
    """PROFIT is aged past FRESHNESS_STALE_S (25s >= 20s) in this fixture --
    see module docstring for why the A_DIM attr itself is proven by a
    separate unit test rather than through this pty/pyte replay."""
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    hud = regions["right_gutter"]
    assert hud is not None
    grid = pyte_grid(_full_tier_stale_fixture_capture, FULL_ROWS, FULL_COLS)
    hud_text = "\n".join(grid[hud["y"] : hud["y"] + hud["h"]])
    normalized = hud_text.replace(",", "").replace("+", "")

    assert "500" in normalized, f"expected stale PROFIT value in HUD box, got:\n{hud_text}"
    assert "ago" in hud_text, f"expected the stale value's own freshness stamp, got:\n{hud_text}"


# ---------------------------------------------------------------------------
# Untrusted HUD content (review REVISE, HIGH): a wire-derived HUD value can
# be an arbitrary string -- ``compose_hud_cells`` renders a non-numeric
# value verbatim (hud.py's own "value formatting" docstring section) and
# only clips it by CODE-POINT count (hud.py: "the curses draw layer is the
# real cell-width backstop"). The REAL choke point is
# ``cockpit_draw.draw_lines_attrs`` -> ``_safe_write`` (sanitize + cell-clip)
# -- these two fixtures prove that choke point is actually on the HUD path,
# mirroring ``tests/test_cockpit_frame_pty.py``'s CJK/control-char hazard
# tests for the LOGS status_line.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _full_tier_cjk_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hud_full_cjk")
    return _drive_hud_pty(tmp_path, FULL_ROWS, FULL_COLS, hud_fixture="cjk")


@pytest.fixture(scope="module")
def _full_tier_escape_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hud_full_escape")
    return _drive_hud_pty(tmp_path, FULL_ROWS, FULL_COLS, hud_fixture="escape")


@_PTY_SKIP
def test_full_tier_cjk_credits_value_preserves_hud_right_border(_full_tier_cjk_fixture_capture):
    """CREDITS' value is 40 CJK/fullwidth glyphs (2 cells each) -- 80 cells
    against the HUD box's ~34-cell interior. ``compose_hud_cells`` only
    clips by Python-character count (still lets ~34+ of the 40 glyphs
    through, i.e. ~68+ cells' worth); the box's own right border must
    survive only because ``draw_lines_attrs``'s ``_clip_cells`` re-clips by
    DISPLAY WIDTH at the draw layer."""
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    hud = regions["right_gutter"]
    assert hud is not None
    screen = pyte_screen(_full_tier_cjk_fixture_capture, FULL_ROWS, FULL_COLS)

    # CREDITS is the first field -- its value row is the box's interior row 1
    # (row 0 is the CREDITS label).
    value_row = hud["y"] + 2
    right_border_x = hud["x"] + hud["w"] - 1
    assert screen.buffer[value_row][right_border_x].data == "│", (
        "CJK-heavy CREDITS value bled past the HUD box's own right border"
    )


@_PTY_SKIP
def test_full_tier_escape_sequence_value_neutralized_not_interpreted(
    _full_tier_escape_fixture_capture,
):
    """CREDITS' value carries a raw ``ESC[2J`` (erase-display) control
    sequence. If ``_sanitize_controls`` didn't run on the HUD path, pyte
    would interpret the real escape byte and clear the whole screen when it
    reaches the terminal -- mirrors
    ``tests/test_cockpit_frame_pty.py::test_embedded_newline_in_status_line_does_not_escape_box``'s
    control-char-neutralization proof, applied to a HUD value field instead
    of ``status_line``."""
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    hud = regions["right_gutter"]
    outer = regions["outer"]
    assert hud is not None
    grid = pyte_grid(_full_tier_escape_fixture_capture, FULL_ROWS, FULL_COLS)
    text = "\n".join(grid)

    # The neutralized ESC becomes a plain space -- "[2Jinjected" survives as
    # literal, harmless text. Had the real escape been interpreted, this
    # substring would never appear (consumed as a control sequence instead
    # of printed), and the chrome checked below would be wiped.
    assert "2Jinjected" in text, (
        f"expected the neutralized escape sequence to render as literal text, got:\n{text}"
    )
    assert "PLAY SHELL" in grid[outer["y"]], "outer frame chrome missing -- screen may have cleared"
    hud_text = "\n".join(grid[hud["y"] : hud["y"] + hud["h"]])
    assert "SECTOR" in hud_text, "HUD's own sibling label missing -- screen may have cleared"


# ---------------------------------------------------------------------------
# Unit-level (no pty): stale-value A_DIM / label+fresh A_NORMAL attr mapping
# at the exact draw call -- the pyte substitution this module's docstring
# discloses.
# ---------------------------------------------------------------------------


class _AttrRecordingWin:
    """Minimal fake curses window recording every ``addstr`` call's
    ``(y, x, text, attr)`` -- unlike
    ``tests/test_cockpit_goals_pty.py::_RecordingWin`` (which records only
    the character grid), this test needs the ``attr`` argument itself, so
    it is kept local rather than shared."""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows, self.cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self.rows, self.cols

    def erase(self) -> None:
        self.calls = []

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def refresh(self) -> None:
        return None


_FIXTURE_CELLS: list[tuple[str, bool]] = [
    ("CREDITS", False),
    ("54,321", False),
    ("SECTOR", False),
    ("1234", False),
    ("TURNS", False),
    ("42", False),
    ("CARGO", False),
    ("3", False),
    ("PROFIT", False),
    ("+500", True),  # the one stale value row in this fixture
]


def test_hud_stale_value_rows_dim_label_rows_stay_normal(monkeypatch):
    """The exact ``attr`` argument ``PlayShellScreen.draw()`` passes per HUD
    row: ``curses.A_DIM`` iff the composer marked that row ``stale``,
    ``curses.A_NORMAL`` for every label row and every fresh value row --
    proven directly at the ``addstr`` call, not inferred from pyte (which
    cannot see SGR-2 dim)."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    monkeypatch.setattr(
        screens_mod.cockpit_hud, "compose_hud_cells", lambda *a, **k: _FIXTURE_CELLS
    )

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _AttrRecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.status_provider = lambda: {"hud": {}}  # any non-None snapshot; composer stubbed above

    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    hud = regions["right_gutter"]
    assert hud is not None
    inner_y, inner_x = hud["y"] + 1, hud["x"] + 1

    calls_by_pos = {(y, x): (text, attr) for (y, x, text, attr) in win.calls}
    for i, (text, stale) in enumerate(_FIXTURE_CELLS):
        pos = (inner_y + i, inner_x)
        assert pos in calls_by_pos, f"no addstr recorded at HUD row {i} ({pos}); calls={win.calls}"
        recorded_text, attr = calls_by_pos[pos]
        assert recorded_text == text, f"row {i}: expected text {text!r}, got {recorded_text!r}"
        expected_attr = curses.A_DIM if stale else curses.A_NORMAL
        assert attr == expected_attr, (
            f"row {i} ({text!r}): expected attr {expected_attr} "
            f"({'A_DIM' if stale else 'A_NORMAL'}), got {attr}"
        )


# ---------------------------------------------------------------------------
# Poll-guard starvation class (PWO-037 dispatch item #2). See module-level
# NOTE: an exhaustive frame_layout probe across the CURRENT MIN_LINES=20 /
# HUD_BOX_MIN_H=12 constants found NO reachable terminal size where
# `decisions` drops to None while `right_gutter` (HUD) survives -- column_h
# never falls below 14 at the MIN_LINES floor, 2 rows clear of
# HUD_BOX_MIN_H. The guard extension below is real (screens.py's poll
# condition now checks `right_gutter` too) but defensive rather than a
# live-bug fix at today's constants; the second test below synthesizes the
# hypothetical shape directly so the guard EXPRESSION itself is proven
# correct independent of reachability.
# ---------------------------------------------------------------------------


def test_poll_guard_one_call_at_minimal_tier_with_control_strip_as_sole_consumer(monkeypatch):
    """Real (not synthetic) tier: 100x25 lands in ``mode == "minimal"``,
    where ``goals``, ``decisions``, AND ``right_gutter`` are all ``None``
    together (no side gutters at all). Before WO-P3-038 this tier polled
    ZERO times (this test's own prior name/assertion, when the guard had
    only three consumer classes) -- WO-P3-038 added ``control_strip`` as a
    FOURTH consumer class, and unlike the ``right_gutter`` extension above
    (defensive/latent at today's constants), ``control_strip`` is present
    at every reachable non-``too_small`` tier (``layout.py``'s own
    ``CONTROL_STRIP_H`` comment) -- INCLUDING this exact real tier. So this
    tier now genuinely polls once, live, not defensively; see
    ``tests/test_cockpit_liveness_pty.py``'s own poll-guard tests for the
    WO-P3-038 side of this guard extension, and ``screens.py``'s own
    comment on the 4th guard term for the full disclosure."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    minimal_rows, minimal_cols = 25, 100
    regions = frame_layout(minimal_rows, minimal_cols)
    assert regions["mode"] == "minimal"
    assert regions["goals"] is None
    assert regions["decisions"] is None
    assert regions["right_gutter"] is None
    assert regions["control_strip"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _AttrRecordingWin(minimal_rows, minimal_cols)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"credits": 1}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll now that control_strip is a "
        f"live status consumer at this tier, got {len(calls)}"
    )


def test_poll_guard_fires_when_hud_is_sole_surviving_status_consumer(monkeypatch):
    """PWO-037 guard-extension regression. Synthesizes the exact
    hypothetical starvation shape (``goals``/``decisions`` both ``None``,
    ``right_gutter`` alone present) by monkeypatching ``frame_layout``'s
    return value on top of a REAL ``right_gutter``-mode regions dict (the
    118..138-col band, where ``goals`` is already ``None``) -- only
    ``decisions`` is forced to the hypothetical ``None``. Proves the guard
    still polls in that shape, independent of whether today's real geometry
    ever reaches it (a future MIN_LINES change could)."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    real_rows, real_cols = 20, 120
    real_regions = frame_layout(real_rows, real_cols)
    assert real_regions["mode"] == "right_gutter"
    assert real_regions["goals"] is None
    assert real_regions["right_gutter"] is not None
    assert real_regions["decisions"] is not None, (
        "sanity check: this scenario is expected to be unreachable via real "
        "frame_layout at current constants -- if this now fails, the "
        "starvation tier has become real and this test's synthetic shape "
        "should be replaced with a real one"
    )
    hypothetical_regions = dict(real_regions)
    hypothetical_regions["decisions"] = None
    monkeypatch.setattr(screens_mod, "frame_layout", lambda *_a, **_k: hypothetical_regions)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _AttrRecordingWin(real_rows, real_cols)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"credits": 1}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll when HUD is the sole "
        f"surviving status consumer, got {len(calls)}"
    )


# ---------------------------------------------------------------------------
# D5 static check: HUD carries no AI-drives badge, and (mirroring
# decisions.py's own check) no send/socket-write call shape -- display-only.
# ---------------------------------------------------------------------------


_TRIPLE_QUOTED_RE = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')


def _strip_docstrings(src: str) -> str:
    """Drop every triple-quoted block (module + function docstrings) before
    a badge-text scan. ``hud.py``'s own module docstring *names* the D5
    rule it follows ("D5: no ``ai_pilot``/imperative-mood text anywhere"),
    which a naive whole-file substring search flags as a false positive --
    the hazard this check actually guards against is badge text reaching
    RENDERED code (a composed label/value string, a call argument), not a
    docstring discussing the rule itself."""
    return _TRIPLE_QUOTED_RE.sub("", src)


def test_hud_composer_and_wire_have_no_ai_pilot_badge_or_send_surface():
    """D5 (PREP hard-gate): no ``ai_pilot``/``AI-PILOT`` badge text anywhere
    in the HUD composer's or ``screens.py``'s live code (docstrings
    excluded -- see ``_strip_docstrings``) -- HUD is read-only
    tracked-model display, never a live-drive indicator. Also asserts the
    composer itself has no send/socket-write call shape, same static check
    ``tests/test_cockpit_decisions_pty.py`` runs on ``decisions.py``."""
    hud_src = (PROJECT_ROOT / "tw2002_aiclient" / "cockpit" / "hud.py").read_text(
        encoding="utf-8"
    )
    screens_src = (PROJECT_ROOT / "tw2002_aiclient" / "screens.py").read_text(encoding="utf-8")

    badge_re = re.compile(r"ai[_-]pilot", re.IGNORECASE)
    assert not badge_re.search(_strip_docstrings(hud_src)), "ai_pilot badge text found in hud.py"
    assert not badge_re.search(_strip_docstrings(screens_src)), (
        "ai_pilot badge text found in screens.py"
    )

    call_shaped = re.compile(r"\b(?:socket|send_keys|os\.write)\s*\(")
    hits = call_shaped.findall(hud_src)
    assert hits == [], f"unexpected send/socket-write call shape(s) in hud.py: {hits}"


def test_play_shell_screen_handle_key_unchanged_esc_and_q_only(monkeypatch):
    """HUD wiring must not add any new key handling -- Esc still returns
    ``back``, ``q``/``Q`` still return ``quit``, and every other key still
    returns ``None``. Pure unit check, no pty needed. Mirrors
    ``tests/test_cockpit_decisions_pty.py``'s equivalent check."""
    from tw2002_aiclient import screens as screens_mod

    # _init_colors() calls curses.has_colors(), which requires a live
    # initscr() outside a real curses session -- stub it False (monochrome
    # path) same as the sibling pty suites' equivalent unit tests.
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    class _NullWin:
        def getmaxyx(self):
            return (40, 160)

        def erase(self):
            return None

        def addstr(self, *a, **k):
            return None

        def refresh(self):
            return None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(), profile)

    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("Q")) == "quit"
    for key in (curses.KEY_UP, curses.KEY_DOWN, ord("1"), ord("d"), ord(" ")):
        assert screen.handle_key(key) is None
