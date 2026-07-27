"""WO-P5-072 Proof (Layer-B) -- the coverage meter on a real terminal.

Real-curses pty + pyte replay (``tests.pty_helpers``), the same Layer-B
harness ``tests/test_cockpit_teachband_pty.py`` and
``tests/test_cockpit_arm_pty.py`` use for the neighbouring chips on this
row.

# Why this file exists, specifically

``tests/test_cockpit_covermeter.py`` proves the meter's math and honesty;
``tests/test_cockpit_covermeter_wiring.py`` proves it composes onto the
control strip. **Neither can see whether ``screens.py`` actually passes the
meter to the composer** -- both call ``control_seat`` directly. That gap was
measured, not assumed: deleting the ``coverage_meter=meter_chip`` argument
from ``screens.py``'s draw path left both suites fully green. A meter that
is composed correctly and never wired is exactly the "defined-but-unwired"
failure the audit's lens 3 hunts, and it would have shipped invisibly.

This file closes that gap by asserting the meter on the settled cockpit of a
real terminal, which is reachable only through the real draw path.

The meter takes no live input on tip (there is no ledger -- PWO-025 is
PARTIAL, ``LedgerWriter`` deferred in ``session/daemon.py``), so the settled
cockpit renders the honest-unknown reading and one capture is the whole
fixture -- same shape as the teach band's suite, which likewise has no
status to stub into the poll. ``adapters.ensure_session`` is stubbed inside
the spawned process and ``TW_RUN_DIR`` points at an isolated per-test tmp
dir, never ``run/twd.sock``.
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


from tw2002_aiclient.cockpit.covermeter import compose_coverage_meter

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
    bootstrap = tmp_path / "covermeter_pty_bootstrap.py"
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
        f"pty coverage-meter drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return captured


@pytest.fixture(scope="module")
def _capture(tmp_path_factory):
    return _drive(tmp_path_factory.mktemp("covermeter_pty"))


@_PTY_SKIP
def test_coverage_meter_is_visible_on_a_real_terminal(_capture) -> None:
    """The wire pin. Goes red if ``screens.py`` stops passing the meter --
    which is the one failure the two headless suites structurally cannot
    see (see this module's docstring)."""
    meter = compose_coverage_meter(app=None, human=None)
    assert find_text(pyte_grid(_capture, FULL_ROWS, FULL_COLS), meter), (
        f"coverage meter {meter!r} not visible on the settled cockpit; grid:\n"
        + "\n".join(pyte_grid(_capture, FULL_ROWS, FULL_COLS))
    )


@_PTY_SKIP
def test_meter_reads_honest_unknown_not_a_fabricated_share(_capture) -> None:
    """There is no ledger on tip, so a percentage on this screen would be
    invented. Asserts the *absence* of the failure, not just the presence of
    the gauge: a meter reading `COV 0%` would satisfy the test above."""
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    assert find_text(grid, "COV ?")
    assert not find_text(grid, "COV 0%"), "fabricated a 0% share with no ledger"


@_PTY_SKIP
def test_no_ai_slice_on_the_real_cockpit(_capture) -> None:
    """Canon J1 at the last possible layer -- what the operator actually
    sees. The archive rendered `App N / AI N · Hum N` on this very gauge."""
    grid = pyte_grid(_capture, FULL_ROWS, FULL_COLS)
    assert not find_text(grid, "AI 0")
    assert not find_text(grid, "/ AI")
