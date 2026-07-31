"""WO-P5-066 Proof (Layer-B) -- the A/R/T teach band on a real terminal.

Real-curses pty + pyte replay (``tests.pty_helpers``), the same Layer-B
harness ``tests/test_cockpit_arm_pty.py`` and
``tests/test_cockpit_liveness_pty.py`` use for the neighbouring chips on
this very row. ``tests/test_cockpit_teachband.py`` proves composition,
placement and width degradation headlessly; this file proves the one thing
those structurally cannot -- that the band survives real curses, a real
terminal-sized frame, and the pyte replay of what a terminal actually
displays.

The band takes no status input (it is calm-state chrome naming the teach
repertoire, not a state readout), so unlike the ARM suite there is nothing
to stub into the poll -- one capture of the settled cockpit is the whole
fixture. ``adapters.ensure_session`` is stubbed inside the spawned process
and ``TW_RUN_DIR`` points at an isolated per-test tmp dir, the same
isolation convention every sibling cockpit-panel pty suite uses -- never
``run/twd.sock``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from tw2002_aiclient.cockpit.stopbanner import TEACH_LINE
from tw2002_aiclient.cockpit.teachband import compose_teach_band

from .pty_helpers import (
    drive_play_shell_pty,
    find_text,
    pty_curses_supported,
    pyte_grid,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
FULL_ROWS, FULL_COLS = 40, 180

_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

_BOOTSTRAP = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, __PROJECT_ROOT__)

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification="main_command")


adapters.ensure_session = _fake_ensure

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive(tmp_path: Path, *, timeout: float = 20.0) -> bytes:
    bootstrap = tmp_path / "teachband_pty_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP.replace("__PROJECT_ROOT__", repr(str(PROJECT_ROOT))),
        encoding="utf-8",
    )
    capture1, _ = drive_play_shell_pty(
        bootstrap,
        project_root=PROJECT_ROOT,
        rows=FULL_ROWS,
        cols=FULL_COLS,
        handle=HANDLE,
        timeout=timeout,
    )
    return capture1


@pytest.fixture(scope="module")
def _capture(tmp_path_factory):
    return _drive(tmp_path_factory.mktemp("teachband_pty"))


@_PTY_SKIP
def test_teach_band_is_visible_on_a_real_terminal(_capture) -> None:
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    band = compose_teach_band()
    assert find_text(grid, band), (
        f"teach band {band!r} not visible on the settled cockpit; grid:\n"
        + "\n".join(grid)
    )


@_PTY_SKIP
def test_each_teach_token_is_individually_visible(_capture) -> None:
    """Guards the failure where the row renders but a token is clipped.

    WO-PLAY-STRIP-TRAINER-CHROME retired the developer A/R/T/V/U/P-panic
    tokens from this calm band -- the trainer's own six tokens replace
    them."""
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    for token in (
        "E)xplore", "P)ort Trade", "L)oops", "T)rade Loop Chain",
        "C)argo Hold Upgrade", "S)hip Upgrade",
    ):
        assert find_text(grid, token), f"token {token!r} not visible"


@_PTY_SKIP
def test_calm_cockpit_shows_the_standing_spelling_not_the_banner_s(_capture) -> None:
    """The register check, at the terminal.

    A calm cockpit (no STOP) must show the standing band's own
    ``T)rade Loop Chain`` token and must NOT be showing the banner's
    ``T)assign`` line -- if the two registers were ever collapsed into one
    constant, this is where it surfaces as something a human would
    actually see.
    """
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    assert find_text(grid, "T)rade Loop Chain")
    assert not find_text(grid, "T)assign"), (
        "the STOP banner's teach spelling is on screen with no halt in "
        "progress -- the two registers have been collapsed"
    )
    assert not find_text(grid, TEACH_LINE)


@_PTY_SKIP
def test_band_shares_the_control_strip_row_with_liveness(_capture) -> None:
    """Canon places the hint band on the control strip, right-aligned,
    yielding to the row's other content -- not on a row of its own."""
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    band = compose_teach_band()
    rows = [i for i, line in enumerate(grid) if band in line]
    assert rows, "band not found on any row"
    _assert_band_right_aligned_on_row(grid[rows[0]], band)


def _assert_band_right_aligned_on_row(row: str, band: str) -> None:
    """Shared right-align pin — production pty capture and left-shift falsify.

    ``index(band) > 0`` only ruled out column 0 (#188 F3 / #192); column 1 and
    any mid-row drift still passed. Canon + ``control_seat`` place the band
    against liveness's left edge (one blank each side), yielding the center.
    """
    assert band in row, "band not on row"
    idx = row.index(band)
    end = idx + len(band)
    left = row[:idx]
    assert left and any(not c.isspace() for c in left), (
        f"band hard-left at column {idx}; canon right-aligns it against "
        "yielded right-side content"
    )
    assert left[-1] == " ", "band abuts left-side content"
    stripped = row.rstrip()
    if end == len(stripped):
        return  # flush to visible right edge (no liveness yield in this frame)
    trailing = stripped[end:]
    assert trailing.startswith(" ") and not trailing.startswith("  "), (
        "band not flush to yielded right-side content (expected one blank)"
    )
    assert trailing[1:] and not trailing[1].isspace(), (
        "expected yielded content after band gap; got trailing blank only"
    )


def test_band_right_align_pin_goes_red_when_left_shifted() -> None:
    """Falsify Accept: band at column 1 (old ``> 0`` still green) must redden
    the *same* helper the pty pin uses."""
    band = compose_teach_band()
    # Column 1 + one-blank yield to liveness — the vacuous ``> 0`` floor passes.
    forged = " " + band + " ♥ RX 2s"
    forged = forged + (" " * (FULL_COLS - len(forged)))
    assert forged.index(band) == 1
    with pytest.raises(AssertionError, match="hard-left|right-align"):
        _assert_band_right_aligned_on_row(forged, band)
