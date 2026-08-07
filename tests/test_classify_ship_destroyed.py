"""WO-FIX-EXPLORE-SHIP-DESTRUCTION-HANG: ship destruction must beat
stale Sector body (else explore mid-warp continue spins forever)."""

from __future__ import annotations

from pathlib import Path

from tw2002_aiclient.session.classify import (
    NEVER_AUTO_ACTION_CLASSES,
    _RETURNABLE_CLASSES,
    classify_screen,
)
from tw2002_aiclient.session.sector_explore import (
    HALT_SHIP_DESTROYED,
    _gate_screen,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _classify(text: str) -> str:
    lines = text.splitlines()
    prompt = lines[-1].strip() if lines else ""
    return classify_screen(text, prompt)


def test_ship_destroyed_beats_sector_body():
    text = (FIXTURES / "ship_destroyed_gone_rogue.txt").read_text(encoding="utf-8")
    assert _classify(text) == "ship_destroyed"


def test_ship_destroyed_beats_sector_even_with_bbs_door_below():
    """Scrollback retained Sector + destruction + outer door — still death."""
    text = (FIXTURES / "ship_destroyed_then_bbs_door.txt").read_text(encoding="utf-8")
    assert _classify(text) == "ship_destroyed"


def test_plain_sector_still_sector_display():
    text = "Sector  : 1234 in uncharted space.\nWarps to Sector(s) :  1 - 2\n\nCommand [TL=00:00:00]:[1234] (?=Help)? : "
    assert _classify(text) == "main_command"


def test_gate_returns_named_halt_ship_destroyed():
    text = (FIXTURES / "ship_destroyed_gone_rogue.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    prompt = lines[-1].strip()
    halt, klass = _gate_screen(text, prompt)
    assert klass == "ship_destroyed"
    assert halt == HALT_SHIP_DESTROYED


def test_ship_destroyed_is_returnable_and_not_never_auto():
    assert "ship_destroyed" in _RETURNABLE_CLASSES
    assert "ship_destroyed" not in NEVER_AUTO_ACTION_CLASSES
