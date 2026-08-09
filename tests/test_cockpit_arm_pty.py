"""WO-P5-062 Accept #4, revised by WO-PLAY-STRIP-TRAINER-CHROME -- the
merged seat+armed chip on a real terminal.

Real-curses pty + pyte replay (``tests.pty_helpers``), the same Layer-B
harness ``tests/test_cockpit_liveness_pty.py`` uses for the neighbouring
liveness cluster on this very row. The headless fake-stdscr suites
(``tests/test_cockpit_arm_wiring.py``) prove the wiring and the placement
logic; this file proves the one thing they structurally cannot -- that the
chip survives real curses, a real terminal-sized frame, and the pyte
replay of what a terminal would actually display.

DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 1 retires the
separate, daemon-sourced ARM chip (``ARM ON``/``ARM OFF``/``ARM ?``) this
file used to drive through three daemon states -- the merged trainer chip
(``^A)APP-ARMED``) is a purely LOCAL reading (DECISION point 6) and no
longer varies with what the daemon reports for ``autopilot``. So the
three fixtures below still drive three distinct daemon reports (to prove
the ABSENCE of that old coupling, not its presence), and the assertions
now check that the merged chip renders identically across all three and
that none of the retired chip's own text ever reaches a real screen.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process and ``TW_RUN_DIR`` points at an isolated per-test tmp dir, the
same convention every sibling cockpit-panel pty suite uses -- never
``run/twd.sock``. The armed/disarmed runs additionally stub
``session_cli.send_request`` in the subprocess, which is how a status
payload is injected without a daemon (``app._daemon_status_provider``'s
own docstring names this as the intended test seam).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from tw2002_aiclient.cockpit.control_seat import APP_LABEL, TRAINER_APP_ARMED_LABEL

# Retired separate ARM chip labels -- must never appear on a real screen.
ARM_ON_LABEL = "ARM ON"
ARM_OFF_LABEL = "ARM OFF"
ARM_UNKNOWN_LABEL = "ARM ?"

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

# The status payload the subprocess should report, injected as a JSON
# blob through a __STATUS_JSON__ token rather than through ``str.format``
# -- this bootstrap contains real Python dict/brace syntax of its own, and
# ``format`` would require doubling every one of those braces (a known
# trap in this suite's own history). ``__STATUS_JSON__`` empty means "do
# not stub the poll at all", i.e. exercise the real no-daemon path.
_BOOTSTRAP = r"""
import json
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

_STATUS_JSON = __STATUS_JSON__
if _STATUS_JSON:
    from tw2002_aiclient.session import cli as session_cli

    _payload = json.loads(_STATUS_JSON)

    def _fake_send_request(verb, args=None, **kwargs):
        if verb == "status":
            return _payload
        return {"ok": False, "error": "not_stubbed"}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive_arm_pty(tmp_path: Path, status: dict | None, *, timeout: float = 20.0) -> bytes:
    """Spawn ``app._run`` in a 40x180 pty, Enter through the launcher, and
    capture the settled cockpit frame. ``status`` is the payload the
    stubbed status poll returns, or ``None`` to leave the real no-daemon
    path in place."""
    bootstrap = tmp_path / "arm_pty_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP
        .replace("__PROJECT_ROOT__", repr(str(PROJECT_ROOT)))
        .replace("__STATUS_JSON__", repr(json.dumps(status) if status else "")),
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


def _grid(captured: bytes) -> list[str]:
    return pyte_grid(captured, FULL_ROWS, FULL_COLS)


@pytest.fixture(scope="module")
def _no_daemon_capture(tmp_path_factory):
    return _drive_arm_pty(tmp_path_factory.mktemp("arm_pty_no_daemon"), None)


@pytest.fixture(scope="module")
def _disarmed_capture(tmp_path_factory):
    return _drive_arm_pty(
        tmp_path_factory.mktemp("arm_pty_disarmed"),
        {"ok": True, "connected": True, "autopilot": {"running": False}},
    )


@pytest.fixture(scope="module")
def _armed_capture(tmp_path_factory):
    return _drive_arm_pty(
        tmp_path_factory.mktemp("arm_pty_armed"),
        {"ok": True, "connected": True, "autopilot": {"running": True}},
    )


@_PTY_SKIP
def test_the_merged_seat_chip_is_visible_on_a_real_terminal(_no_daemon_capture):
    """DECISION point 1/6: with no daemon at all there is no evidence
    about the autopilot, yet the merged chip still claims ``-ARMED`` --
    it is this client's own local reading of "App holds the seat," not a
    daemon-verified fact, so having zero evidence about the daemon does
    not blank it or degrade it to an unknown state the way the retired
    ARM chip once did."""
    grid = _grid(_no_daemon_capture)
    assert find_text(grid, TRAINER_APP_ARMED_LABEL)
    for retired in (ARM_ON_LABEL, ARM_OFF_LABEL, ARM_UNKNOWN_LABEL):
        assert not find_text(grid, retired)


@_PTY_SKIP
def test_the_merged_chip_shares_its_row_with_the_liveness_cluster(
    _no_daemon_capture,
):
    """The strip's pre-existing, operationally load-bearing "is it
    frozen?" liveness cluster keeps its full space beside the merged
    chip -- unchanged from the pre-merge row's own guarantee."""
    grid = _grid(_no_daemon_capture)
    rows = [line for line in grid if TRAINER_APP_ARMED_LABEL in line and "→" in line]
    assert rows, (
        "expected one row carrying BOTH the merged seat chip and the "
        "liveness cluster; grid:\n" + "\n".join(grid)
    )


@_PTY_SKIP
def test_no_daemon_report_moves_the_merged_chip_on_a_real_screen(
    _no_daemon_capture, _disarmed_capture, _armed_capture
):
    """DECISION point 1/6, the TTY-layer non-vacuity proof: three
    identical runs of the same cockpit differ in one thing only -- what
    the daemon reported for ``autopilot`` -- and the merged chip is
    unmoved by all three, because it no longer reads that payload at all.
    None of the retired chip's own text (``ARM ON``/``ARM OFF``/``ARM
    ?``) reaches a real screen in any of the three."""
    for capture in (_no_daemon_capture, _disarmed_capture, _armed_capture):
        grid = _grid(capture)
        assert find_text(grid, TRAINER_APP_ARMED_LABEL)
        for retired in (ARM_ON_LABEL, ARM_OFF_LABEL, ARM_UNKNOWN_LABEL):
            assert not find_text(grid, retired)


@_PTY_SKIP
def test_the_seat_chip_is_unmoved_by_the_daemons_arm_report(
    _no_daemon_capture, _disarmed_capture, _armed_capture
):
    """The hazard, proved end to end on a real terminal: ARM is not the
    human lock. The arm reading swings across all three of its states and
    the seat chip stays ``APP`` throughout -- arming never took, released,
    or appeared to change the seat."""
    for capture in (_no_daemon_capture, _disarmed_capture, _armed_capture):
        grid = _grid(capture)
        assert find_text(grid, APP_LABEL)
        assert not find_text(grid, "MANUAL")
        assert not find_text(grid, "SPECTATE")
