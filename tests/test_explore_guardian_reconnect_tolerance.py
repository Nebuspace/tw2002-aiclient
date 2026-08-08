"""WO-DIAGNOSE-EXPLORE-HALT-GAME-SELECT-LIVE-SESSION.

# The defect, reproduced from a live scout_academy run

`tw explore start` halted immediately (`halt_not_drivable:game_select`,
zero sends) on a daemon `tw status`, queried moments later, still reported
as `connected: true` / `classification: "main_command"` — see
`canon/research/autopilot-live-drive-findings-2026-08-08.md` Axis 5.

# The mechanism

`ExploreRunner._run` reads and classifies the session's LIVE screen with no
coordination with `SessionGuardian`'s own D9 reconnect+login-replay burst
(`guardian.py`) — confirmed by grep: before this WO, zero non-guardian
module read `_reconnect_in_flight` anywhere in the tree. A guardian burst
that is mid-replay legitimately passes through `game_select` (a multi-game
BBS shows the game-select menu before the replay's login automaton picks a
game letter again) — a screen the explorer's own gate correctly treats as
"not drivable" when reached genuinely, but which is a TRANSIENT artifact of
the guardian's own in-flight recovery here, not a real halt condition.

# What is pinned

* A halt-classified screen reached while `guardian.reconnecting` is True
  does NOT halt the run — it waits (bounded) and re-classifies once the
  burst clears.
* The same screen, reached with NO guardian (the pre-fix constructor
  default, still every other test in this file's siblings) or with a
  guardian that is not mid-burst, halts exactly as before — this is a
  tolerance window, never a behavior change for a genuine halt.
* A burst that never clears within the (monkeypatched-short, here) bound
  still halts — the wait is bounded, not a substitute for the guardian's
  own `reconnect_exhausted` handling.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from tw2002_aiclient.loops.player import OUTCOME_HALTED
from tw2002_aiclient.session import sector_explore
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

WORLD = "explore-guardian-reconnect+G+CAP"

GAME_SELECT_SCREEN = (
    "Games available :\n\n  A) TradeWars Game A\n  B) TradeWars Game B\n\nSelect a game :"
)
MAIN_COMMAND_SCREEN = "Command [TL=00:00:00]:[42] (?=Help)? : "


class _FakeGuardian:
    def __init__(self, reconnecting: bool):
        self.reconnecting = reconnecting


def _fast_bounds(monkeypatch):
    """Every test here uses a short bound -- the real 30s default would
    make the "burst never clears" test genuinely take 30 real seconds."""
    monkeypatch.setattr(sector_explore, "RECONNECT_WAIT_TIMEOUT_S", 0.3)
    monkeypatch.setattr(sector_explore, "RECONNECT_WAIT_POLL_S", 0.05)


def test_no_guardian_halts_exactly_as_before(tmp_path: Path, monkeypatch):
    """Default constructor (guardian=None, the shape every pre-existing
    test in test_sector_explore.py already uses) is unaffected."""
    _fast_bounds(monkeypatch)
    session = FakeAttachSession(initial_screen=GAME_SELECT_SCREEN)
    session.rx_count = 1
    session.last_rx = -10.0
    lock = ControlLock()
    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path)
    runner.start(WORLD, min_sectors=5, turn_budget=10)
    runner._thread.join(timeout=15)
    report = runner.snapshot().report
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "halt_not_drivable:game_select"


def test_guardian_not_reconnecting_halts_exactly_as_before(tmp_path: Path, monkeypatch):
    _fast_bounds(monkeypatch)
    session = FakeAttachSession(initial_screen=GAME_SELECT_SCREEN)
    session.rx_count = 1
    session.last_rx = -10.0
    lock = ControlLock()
    guardian = _FakeGuardian(reconnecting=False)
    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path, guardian=guardian)
    runner.start(WORLD, min_sectors=5, turn_budget=10)
    runner._thread.join(timeout=15)
    report = runner.snapshot().report
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "halt_not_drivable:game_select"


def test_reconnect_burst_that_never_clears_still_halts(tmp_path: Path, monkeypatch):
    """The wait is bounded -- a stuck/exhausted burst does not hang the
    run forever, it eventually falls through to the ordinary halt."""
    _fast_bounds(monkeypatch)
    session = FakeAttachSession(initial_screen=GAME_SELECT_SCREEN)
    session.rx_count = 1
    session.last_rx = -10.0
    lock = ControlLock()
    guardian = _FakeGuardian(reconnecting=True)
    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path, guardian=guardian)
    runner.start(WORLD, min_sectors=5, turn_budget=10)
    runner._thread.join(timeout=15)
    report = runner.snapshot().report
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "halt_not_drivable:game_select"


def test_reconnect_burst_that_clears_lets_the_run_continue(tmp_path: Path, monkeypatch):
    """The evidenced fix: a screen classified game_select WHILE a guardian
    burst is in flight is tolerated -- once the burst clears (here,
    flipped by a background thread simulating the guardian's own login
    replay completing) and the screen has moved on to something drivable,
    the run proceeds instead of halting on the transient artifact."""
    _fast_bounds(monkeypatch)
    session = FakeAttachSession(initial_screen=GAME_SELECT_SCREEN)
    session.rx_count = 1
    session.last_rx = -10.0
    lock = ControlLock()
    guardian = _FakeGuardian(reconnecting=True)

    def _finish_reconnect_burst():
        time.sleep(0.1)
        session._screen = MAIN_COMMAND_SCREEN
        session.rx_count += 1
        session.last_rx = time.monotonic()
        guardian.reconnecting = False

    threading.Thread(target=_finish_reconnect_burst, daemon=True).start()

    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path, guardian=guardian)
    runner.start(WORLD, min_sectors=1, turn_budget=5)
    runner._thread.join(timeout=15)
    report = runner.snapshot().report
    assert report is not None
    assert report.reason != "halt_not_drivable:game_select", report.reason
