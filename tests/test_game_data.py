"""TW-24 game_data schema/loader tests."""

from pathlib import Path

import pytest

from twclient.game_data import (
    empty_game_data,
    load_game_data,
    ship_row_to_spec,
    validate_ship_row,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_game_data.json"


def test_load_fixture_scout_is_introspected():
    data = load_game_data(FIXTURE)
    assert len(data.ships) == 1
    ship = data.ships[0]
    assert ship.ship_name == "Fixture Scout"
    assert ship.source.startswith("introspected")
    assert ship.max_holds == 10
    assert data.world_id == "fixture+test"


def test_reject_authored_source():
    row = {
        "ship_name": "Bad",
        "max_holds": 1,
        "max_fighters": 0,
        "max_shields": 0,
        "combat_odds_modifier": 1.0,
        "turns_per_warp": 3,
        "base_cost_credits": 1,
        "alignment_requirement": None,
        "rank_requirement": None,
        "transwarp_capable": False,
        "special_abilities": [],
        "source": "authored: wiki",
        "last_verified_ts": "2026-07-19T00:00:00Z",
    }
    with pytest.raises(ValueError, match="introspected"):
        validate_ship_row(row)


def test_reject_missing_max_holds():
    row = {
        "ship_name": "Bad",
        "max_fighters": 0,
        "max_shields": 0,
        "combat_odds_modifier": 1.0,
        "turns_per_warp": 3,
        "base_cost_credits": 1,
        "alignment_requirement": None,
        "rank_requirement": None,
        "transwarp_capable": False,
        "special_abilities": [],
        "source": "introspected: test",
        "last_verified_ts": "2026-07-19T00:00:00Z",
    }
    with pytest.raises(ValueError, match="max_holds"):
        validate_ship_row(row)


def test_empty_game_data_has_no_ships():
    assert empty_game_data().ships == ()


def test_ship_row_to_spec_bridge():
    ship = load_game_data(FIXTURE).ships[0]
    spec = ship_row_to_spec(ship)
    assert spec.name == "Fixture Scout"
    assert spec.holds == 10
    assert spec.cost == 1000
    assert spec.turns_per_warp == 3
