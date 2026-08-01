"""WO-EXPLORE-MIDWARP-WAIT: intentional hop must wait through mid-warp
``sector_display`` frames instead of ``halt_not_drivable:sector_display``."""

from __future__ import annotations

import time

from tw2002_aiclient import world_model
from tw2002_aiclient.loops.player import OUTCOME_COMPLETED, OUTCOME_HALTED
from tw2002_aiclient.session import sector_explore as sx
from tw2002_aiclient.session.classify import classify_screen
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

WORLD = "w-midwarp-wait"

SECTOR_SRC = (
    "Sector  : 100 in uncharted space.\n"
    "Warps to Sector(s) :  (200)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[100] (?=Help)? : "
)

SECTOR_DST = (
    "Sector  : 200 in uncharted space.\n"
    "Warps to Sector(s) :  (100) - (300)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[200] (?=Help)? : "
)

SECTOR_DST2 = (
    "Sector  : 300 in uncharted space.\n"
    "Warps to Sector(s) :  (200)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[300] (?=Help)? : "
)

MIDWARP_PROGRESS = (
    "<Move>\n"
    "Warping to Sector 200\n"
    "\n"
    "\n"
    "│██████████          │\n"
)

MIDWARP_BODY = (
    "Sector  : 200 in uncharted space.\n"
    "Warps to Sector(s) :  (100) - (300)\n"
)


class _MidwarpThenArriveSession(FakeAttachSession):
    """main_command → hop → progress (sector_display) → body → dest Command."""

    def __init__(self):
        super().__init__(initial_screen=SECTOR_SRC)
        self.rx_count = 1
        self.last_rx = -10.0
        self._phase = "src"
        self._frames_after_hop = 0

    def send(self, text, enter=True, secret=False, sender="app"):
        key = text.strip()
        if self._phase == "src" and key == "200":
            self._screen = MIDWARP_PROGRESS
            self._phase = "midwarp"
            self._frames_after_hop = 0
        elif self._phase == "dst" and key == "300":
            self._screen = SECTOR_DST2
            self._phase = "dst2"
        return super().send(text, enter=enter, secret=secret, sender=sender)

    def render(self):
        if self._phase == "midwarp":
            self._frames_after_hop += 1
            if self._frames_after_hop == 2:
                self._screen = MIDWARP_BODY
            elif self._frames_after_hop >= 3:
                self._screen = SECTOR_DST
                self._phase = "dst"
                self.rx_count += 1
                self.last_rx = -10.0
        return super().render()


def _run_until_finished(session, tmp_path, *, min_sectors=3, turn_budget=10, timeout_s=10.0):
    # Seed ONLY the current sector so map-fill hops into unknowns.
    world_model.upsert_sector(
        WORLD, {"sector_id": 100, "warps": [200], "landmarks": []}, state_dir=tmp_path
    )
    runner = sx.ExploreRunner(
        session, ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    runner.start(
        WORLD,
        min_sectors=min_sectors,
        turn_budget=turn_budget,
        dock_new_ports=False,
        fight_tolls=False,
    )
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline:
            snap = runner.snapshot()
            if snap.report is not None and snap.report.outcome is not None:
                return snap.report
            time.sleep(0.02)
        return None
    finally:
        runner.stop(join_timeout=5.0)


def test_midwarp_progress_classifies_as_sector_display():
    assert classify_screen(MIDWARP_PROGRESS, "│██████████          │") == "sector_display"
    assert classify_screen(MIDWARP_BODY, "Warps to Sector(s) :  (100) - (300)") == (
        "sector_display"
    )
    assert classify_screen(SECTOR_DST, "Command [TL=00753:0/0/0/850]:[200] (?=Help)? :") == (
        "main_command"
    )


def test_explore_waits_through_midwarp_sector_display(tmp_path):
    session = _MidwarpThenArriveSession()
    report = _run_until_finished(session, tmp_path, min_sectors=3, turn_budget=10)
    assert report is not None
    assert report.reason != "halt_not_drivable:sector_display", report.reason
    assert report.distinct_sectors >= 2, report
    assert "200" in [t[0].strip() for t in session.sent]
    assert report.outcome in (OUTCOME_COMPLETED, OUTCOME_HALTED)


def test_sector_display_without_pending_hop_still_halts(tmp_path):
    class _StuckDisplay(FakeAttachSession):
        def __init__(self):
            super().__init__(initial_screen=MIDWARP_BODY)
            self.rx_count = 1
            self.last_rx = -10.0

    report = _run_until_finished(_StuckDisplay(), tmp_path, min_sectors=5, turn_budget=5)
    assert report is not None
    assert report.reason == "halt_not_drivable:sector_display"
