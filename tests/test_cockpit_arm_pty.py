"""WO-P5-062 Accept #4 -- the ARM indicator on a real terminal.

Real-curses pty + pyte replay (``tests.pty_helpers``), the same Layer-B
harness ``tests/test_cockpit_liveness_pty.py`` uses for the neighbouring
liveness cluster on this very row. The headless fake-stdscr suites
(``tests/test_cockpit_arm_wiring.py``) prove the wiring and the placement
logic; this file proves the one thing they structurally cannot -- that the
chip survives real curses, a real terminal-sized frame, and the pyte
replay of what a terminal would actually display.

Three states are driven through a real TTY:

  - **no daemon** -> ``ARM ?``. This is the honest default and the one a
    developer will see most often. The status poll early-returns
    ``daemon_not_running`` without opening a socket, so there is no
    evidence about the autopilot either way, and the chip says so rather
    than rendering a calm ``ARM OFF`` nobody could stand behind.
  - **daemon reporting disarmed** -> ``ARM OFF``, the reading a live
    daemon produces today.
  - **daemon reporting armed** -> ``ARM ON``, which nothing but the
    daemon's own report can produce (the non-vacuity companion, at the
    TTY layer this time).

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


from tw2002_aiclient.cockpit.arm import ARM_OFF_LABEL, ARM_ON_LABEL, ARM_UNKNOWN_LABEL
from tw2002_aiclient.cockpit.control_seat import APP_LABEL

from .pty_helpers import (
    drive_play_shell_pty,
    find_text,
    pty_curses_supported,
    pyte_grid,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
FULL_ROWS, FULL_COLS = 40, 160

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
    """Spawn ``app._run`` in a 40x160 pty, Enter through the launcher, and
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
def test_the_arm_indicator_is_visible_on_a_real_terminal(_no_daemon_capture):
    """Accept #4. With no daemon there is no evidence about the autopilot,
    and the chip says exactly that on a real TTY rather than going blank
    or claiming a calm ``ARM OFF``."""
    grid = _grid(_no_daemon_capture)
    assert find_text(grid, ARM_UNKNOWN_LABEL)
    assert not find_text(grid, ARM_ON_LABEL)


@_PTY_SKIP
def test_the_seat_chip_and_the_arm_chip_are_both_visible_on_the_same_row(
    _no_daemon_capture,
):
    """Accept #1 at the terminal: the two facts sit side by side on one
    row, separately legible. The cockpit's entry seat is App-hold, so the
    row reads ``APP`` then the arm chip -- who holds the keyboard, then
    whether the taught autopilot may act."""
    grid = _grid(_no_daemon_capture)
    rows = [line for line in grid if APP_LABEL in line and ARM_UNKNOWN_LABEL in line]
    assert rows, (
        "expected one row carrying BOTH the seat chip and the arm chip; grid:\n"
        + "\n".join(grid)
    )
    row = rows[0]
    assert row.index(APP_LABEL) < row.index(ARM_UNKNOWN_LABEL)
    # The liveness cluster the strip already carried still shares the row.
    assert "→" in row


@_PTY_SKIP
def test_a_daemon_reporting_disarmed_renders_the_disarmed_chip(_disarmed_capture):
    """The reading a live daemon produces today -- ``session/protocol.py``
    reports its hardcoded ``{"running": False}``, and the round trip ends
    with that fact on the operator's screen."""
    grid = _grid(_disarmed_capture)
    assert find_text(grid, ARM_OFF_LABEL)
    assert not find_text(grid, ARM_ON_LABEL)
    assert not find_text(grid, ARM_UNKNOWN_LABEL)


@_PTY_SKIP
def test_only_the_daemons_own_report_can_put_armed_on_a_real_screen(_armed_capture):
    """Accept #2 and the TTY-layer non-vacuity companion for Accept #3.
    Three identical runs of the same cockpit differ in one thing only --
    what the daemon reported -- and the chip tracks it. So the indicator
    genuinely reflects the daemon's state rather than a local guess, and
    the ``ARM ON`` absent from the other two captures was absent because
    nothing reported it, not because the chip cannot say it."""
    grid = _grid(_armed_capture)
    assert find_text(grid, ARM_ON_LABEL)
    assert not find_text(grid, ARM_UNKNOWN_LABEL)


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
