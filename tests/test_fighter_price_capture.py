"""WO-AICLIENT-WIRE-FIGHTER-PRICE-OBSERVE-FROM-SCREEN — idle-tick observe wire."""

from __future__ import annotations

import ast
from pathlib import Path

from tw2002_aiclient import fighter_price_capture as fpc
from tw2002_aiclient.fighter_price_status import (
    CLASS0_PRICE_KEY,
    UNIT_PRICE_KEY,
    FighterPriceScalars,
)


class _Snap:
    def __init__(self, latest_event: dict | None) -> None:
        self.latest_event = latest_event


class _Play:
    def __init__(self, event: dict | None, *, scalars: FighterPriceScalars | None = None) -> None:
        self._event = event
        self.viewport_provider = lambda: _Snap(self._event)
        self.fighter_price_scalars = scalars if scalars is not None else FighterPriceScalars()


def test_tick_observes_price_from_watch_event() -> None:
    play = _Play(
        {
            "ok": True,
            "screen": ["Fighters cost 100 credits each.", "Command [TL=00:00:00]:"],
            "prompt": "Command [TL=00:00:00]:",
        }
    )
    result = fpc.FighterPriceCapture().tick(play)
    assert result.attempted is True
    assert result.unit_price == 100
    merged = play.fighter_price_scalars.merge({})
    assert merged[UNIT_PRICE_KEY] == 100
    assert merged[CLASS0_PRICE_KEY] == 100


def test_tick_fail_closed_no_match() -> None:
    play = _Play(
        {
            "ok": True,
            "screen": ["Sector 123", "Command [TL=00:00:00]:"],
            "prompt": "Command [TL=00:00:00]:",
        }
    )
    result = fpc.FighterPriceCapture().tick(play)
    assert result.attempted is False
    assert result.reason == "no_price_match"
    assert play.fighter_price_scalars.merge({}) == {}


def test_tick_dedupes_unchanged_fingerprint() -> None:
    event = {
        "ok": True,
        "screen": ["150 credits per fighter", "Command:"],
        "prompt": "Command:",
    }
    play = _Play(event)
    cap = fpc.FighterPriceCapture()
    first = cap.tick(play)
    second = cap.tick(play)
    assert first.attempted is True
    assert first.unit_price == 150
    assert second.attempted is False
    assert second.reason == "unchanged"


def test_tick_no_event() -> None:
    play = _Play(None)
    result = fpc.FighterPriceCapture().tick(play)
    assert result.attempted is False
    assert result.reason == "no_event"


def test_tick_missing_scalars_contained() -> None:
    play = _Play({"ok": True, "screen": ["Fighters cost 100 credits each."]})
    del play.fighter_price_scalars
    result = fpc.FighterPriceCapture().tick(play)
    assert result.attempted is False
    assert result.reason == "no_scalars"


def test_app_idle_tick_wires_fighter_price_capture() -> None:
    src = Path("tw2002_aiclient/app.py").read_text(encoding="utf-8")
    assert "fighter_price_capture" in src
    assert "FighterPriceCapture" in src
    assert "fighter_price_capture.tick" in src
    assert ast.parse(src) is not None
