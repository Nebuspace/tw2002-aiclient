"""WO-WARP-CONFIRM-Y: intentional hop + warp_confirm → Y; no hop → no Y."""

from __future__ import annotations

import time
from pathlib import Path

from tw2002_aiclient import world_model
from tw2002_aiclient.loops.player import OUTCOME_COMPLETED, OUTCOME_HALTED
from tw2002_aiclient.session import sector_explore as sx
from tw2002_aiclient.session.classify import classify_screen
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

WORLD = "w-warp-confirm"

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WARP_CONFIRM = (FIXTURES / "warp_confirm_prompt.txt").read_text(encoding="utf-8")

SECTOR_SRC = (
    "Sector  : 100 in uncharted space.\n"
    "Warps to Sector(s) :  (200)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[100] (?=Help)? : "
)

SECTOR_DST = (
    "Sector  : 200 in uncharted space.\n"
    "Warps to Sector(s) :  (100)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[200] (?=Help)? : "
)


class _WarpConfirmAfterHopSession(FakeAttachSession):
    """main_command → hop send → warp_confirm → Y → destination main_command."""

    def __init__(self):
        super().__init__(initial_screen=SECTOR_SRC)
        self.rx_count = 1
        self.last_rx = -10.0
        self._phase = "src"

    def send(self, text, enter=True, secret=False, sender="app"):
        key = text.strip()
        if self._phase == "src" and key == "200":
            self._screen = WARP_CONFIRM
            self._phase = "confirm"
        elif self._phase == "confirm" and key.upper() == "Y":
            self._screen = SECTOR_DST
            self._phase = "dst"
        return super().send(text, enter=enter, secret=secret, sender=sender)


class _WarpConfirmNoHopSession(FakeAttachSession):
    """Settled on warp_confirm with no prior intentional hop."""

    def __init__(self):
        super().__init__(initial_screen=WARP_CONFIRM)
        self.rx_count = 1
        self.last_rx = -10.0


def _letters(session) -> list[str]:
    return [t[0].strip() for t in session.sent]


def _run_until_finished(session, tmp_path, *, min_sectors=1, turn_budget=5, timeout_s=10.0):
    # Seed ONLY the current sector — pre-knowing 200 makes map-fill report
    # at_densest and never hop (no intentional send → no warp_confirm wire).
    world_model.upsert_sector(
        WORLD, {"sector_id": 100, "warps": [200], "landmarks": []}, state_dir=tmp_path
    )
    runner = sx.ExploreRunner(
        session, ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    runner.start(WORLD, min_sectors=min_sectors, turn_budget=turn_budget)
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


def test_fixture_classifies_warp_confirm():
    text = WARP_CONFIRM.rstrip("\n")
    prompt = text.splitlines()[-1]
    assert classify_screen(text, prompt) == "warp_confirm"


def test_intentional_hop_warp_confirm_sends_y_and_continues(tmp_path):
    session = _WarpConfirmAfterHopSession()
    report = _run_until_finished(session, tmp_path, min_sectors=2, turn_budget=5)
    letters = _letters(session)
    assert "200" in letters
    assert "Y" in letters
    assert letters.index("Y") > letters.index("200")
    assert report.outcome in (OUTCOME_COMPLETED, OUTCOME_HALTED)
    assert report.reason != "halt_not_drivable:warp_confirm"


def test_warp_confirm_without_intentional_hop_does_not_send_y(tmp_path):
    session = _WarpConfirmNoHopSession()
    report = _run_until_finished(session, tmp_path, min_sectors=1, turn_budget=3)
    assert "Y" not in _letters(session)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "halt_not_drivable:warp_confirm"
