"""AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP — opportunistic observe→persist pins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tw2002_aiclient import game_data as gd
from tw2002_aiclient import game_data_capture as gdc

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WORLD_ID = "capture-demo_example__A__Pilot"


@dataclass
class _Snap:
    latest_event: dict | None


class _Play:
    def __init__(self, event: dict | None) -> None:
        self._event = event
        self.viewport_provider = lambda: _Snap(self._event)


class _Profile:
    host, game_letter, handle = "capture-demo.example", "A", "Pilot"


def _event_from_fixture(name: str, classification: str) -> dict:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    return {
        "ok": True,
        "screen": rows,
        "prompt": prompt,
        # Live settle often keeps the gate prompt class; capture keys off
        # listing grammar inside the body, not this label alone.
        "classification": classification,
    }


def test_tick_persists_shipyard_rows(tmp_path: Path):
    play = _Play(_event_from_fixture("stardock_shipyard_listing.txt", "main_command"))
    result = gdc.GameDataCapture().tick(play, _Profile(), state_dir=tmp_path)
    assert result.attempted is True
    assert result.ships_persisted >= 1
    assert result.reason is None
    loaded = gd.load_world_game_data(WORLD_ID, state_dir=tmp_path)
    assert len(loaded.ships) == result.ships_persisted
    assert all(s.source.startswith("introspected") for s in loaded.ships)


def test_tick_skips_main_command_without_listing(tmp_path: Path):
    play = _Play(
        {
            "screen": ["Command [TL=00753:0/0/0/850] (?=Help)? :"],
            "prompt": "Command [TL=00753:0/0/0/850] (?=Help)? :",
            "classification": "main_command",
        }
    )
    result = gdc.GameDataCapture().tick(play, _Profile(), state_dir=tmp_path)
    assert result.attempted is False
    assert result.reason == "no_listing"
    assert gd.load_world_game_data(WORLD_ID, state_dir=tmp_path).ships == ()


def test_tick_dedupes_identical_listing(tmp_path: Path):
    play = _Play(_event_from_fixture("stardock_shipyard_listing.txt", "main_command"))
    cap = gdc.GameDataCapture()
    first = cap.tick(play, _Profile(), state_dir=tmp_path)
    second = cap.tick(play, _Profile(), state_dir=tmp_path)
    assert first.ships_persisted >= 1
    assert second.attempted is False
    assert second.reason == "unchanged"


def test_tick_persists_cargo_hold_quote(tmp_path: Path):
    play = _Play(_event_from_fixture("stardock_cargo_hold_quote.txt", "money_prompt"))
    result = gdc.GameDataCapture().tick(play, _Profile(), state_dir=tmp_path)
    assert result.attempted is True
    assert result.cargo_persisted is True
    loaded = gd.load_world_game_data(WORLD_ID, state_dir=tmp_path)
    assert len(loaded.cargo_holds) == 1
    assert loaded.cargo_holds[0].source.startswith("introspected")


def test_tick_never_raises_on_broken_provider(tmp_path: Path):
    play = _Play(None)
    play.viewport_provider = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    result = gdc.GameDataCapture().tick(play, _Profile(), state_dir=tmp_path)
    assert result.attempted is False


def test_capture_module_has_no_send_symbol():
    """Static Accept: opportunistic path must not grow a send API."""
    banned = {"send", "do", "crawl", "run_live_crawl"}
    assert banned.isdisjoint(set(dir(gdc)))


def test_app_idle_tick_wires_gamedata_capture():
    """Product path: play loop constructs GameDataCapture and ticks it."""
    import inspect
    from tw2002_aiclient import app as app_mod

    src = inspect.getsource(app_mod)
    assert "game_data_capture" in src
    assert "gamedata_capture.tick" in src
