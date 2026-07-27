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

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from tw2002_aiclient.cockpit.stopbanner import TEACH_LINE
from tw2002_aiclient.cockpit.teachband import compose_teach_band

from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
FULL_ROWS, FULL_COLS = 40, 160

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


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining for ``seconds``. One ``refresh()`` of a 40x160 frame
    spans several OS-level pty chunks and the control strip is drawn LAST,
    so a one-shot read can snapshot mid-flush and miss exactly the row this
    file is about (same reason the sibling suites carry this helper)."""
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


def _drive(tmp_path: Path, *, timeout: float = 20.0) -> bytes:
    bootstrap = tmp_path / "teachband_pty_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP.replace("__PROJECT_ROOT__", repr(str(PROJECT_ROOT))),
        encoding="utf-8",
    )
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, FULL_ROWS, FULL_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    for stray in ("TW2002_ASCII", "TW2002_HANDOFF_SMOKE",
                  "TW2002_LAUNCHER_SMOKE", "TW2002_BANK_SMOKE"):
        env.pop(stray, None)

    proc = subprocess.Popen(
        [sys.executable, str(bootstrap)],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
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

            grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)
            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, "PLAY SHELL"):
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
        terminate_session_group(proc, grace_s=5.0)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty teach-band drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return captured


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
    """Guards the failure where the row renders but a token is clipped."""
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    for token in ("A)nalyze", "R)ecord", "T)rigger"):
        assert find_text(grid, token), f"token {token!r} not visible"


@_PTY_SKIP
def test_calm_cockpit_shows_the_standing_spelling_not_the_banner_s(_capture) -> None:
    """The register check, at the terminal.

    A calm cockpit (no STOP) must show the standing band's ``T)rigger``
    and must NOT be showing the banner's ``T)assign`` line -- if the two
    registers were ever collapsed into one constant, this is where it
    surfaces as something a human would actually see.
    """
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    assert find_text(grid, "T)rigger")
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
    row = grid[rows[0]]
    assert row.index(band) > 0, "band is hard-left; canon right-aligns it"
