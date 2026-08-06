"""PWO-092 Option A — game_data kernel: source gate + fixture round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient.game_data import (
    GameDataError,
    empty_game_data,
    game_data_path,
    load_game_data,
    load_world_game_data,
    persist_ship_row,
    save_world_game_data,
    ship_row_to_spec,
    validate_ship_row,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mock_game_data.json"


def test_load_mock_fixture_round_trips_ships():
    data = load_game_data(FIXTURE)
    assert data.world_id == "fixture+test"
    assert len(data.ships) == 1
    ship = data.ships[0]
    assert ship.ship_name == "Fixture Scout"
    assert ship.source.startswith("introspected")
    assert ship.max_holds == 10


def test_source_gate_refuses_static_authored_number():
    row = json.loads(FIXTURE.read_text(encoding="utf-8"))["ships"][0]
    row = dict(row)
    row["source"] = "authored: stock TW2002 table"
    with pytest.raises(GameDataError, match="introspected"):
        validate_ship_row(row)


def test_load_refuses_non_introspected_on_disk(tmp_path):
    bad = {
        "world_id": "w1",
        "ships": [
            {
                "ship_name": "Bad",
                "max_holds": 1,
                "max_fighters": 1,
                "max_shields": 1,
                "combat_odds_modifier": 1.0,
                "turns_per_warp": 1,
                "base_cost_credits": 1,
                "alignment_requirement": None,
                "rank_requirement": None,
                "transwarp_capable": False,
                "special_abilities": [],
                "source": "guessed",
                "last_verified_ts": "2026-08-03T00:00:00Z",
            }
        ],
        "scanners": [],
        "transwarp": [],
        "items": [],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(GameDataError, match="introspected"):
        load_game_data(path)


def test_persist_and_reload_world_store(tmp_path):
    fixture = load_game_data(FIXTURE)
    ship = fixture.ships[0]
    persisted = persist_ship_row(
        "test-world",
        {
            "ship_name": ship.ship_name,
            "max_holds": ship.max_holds,
            "max_fighters": ship.max_fighters,
            "max_shields": ship.max_shields,
            "combat_odds_modifier": ship.combat_odds_modifier,
            "turns_per_warp": ship.turns_per_warp,
            "base_cost_credits": ship.base_cost_credits,
            "alignment_requirement": ship.alignment_requirement,
            "rank_requirement": ship.rank_requirement,
            "transwarp_capable": ship.transwarp_capable,
            "special_abilities": list(ship.special_abilities),
            "source": ship.source,
            "last_verified_ts": ship.last_verified_ts,
        },
        state_dir=tmp_path,
    )
    assert persisted.ship_name == "Fixture Scout"
    path = game_data_path("test-world", state_dir=tmp_path)
    assert path.is_file()
    reloaded = load_world_game_data("test-world", state_dir=tmp_path)
    assert reloaded.world_id == "test-world"
    assert len(reloaded.ships) == 1
    assert reloaded.ships[0].ship_name == "Fixture Scout"


def test_save_world_game_data_refuses_without_world_id(tmp_path):
    with pytest.raises(GameDataError, match="world_id"):
        save_world_game_data(empty_game_data(), state_dir=tmp_path)


def test_persist_refuses_non_introspected_before_write(tmp_path):
    with pytest.raises(GameDataError, match="introspected"):
        persist_ship_row(
            "test-world",
            {
                "ship_name": "X",
                "max_holds": 1,
                "max_fighters": 1,
                "max_shields": 1,
                "combat_odds_modifier": 1.0,
                "turns_per_warp": 1,
                "base_cost_credits": 1,
                "alignment_requirement": None,
                "rank_requirement": None,
                "transwarp_capable": False,
                "special_abilities": [],
                "source": "static",
                "last_verified_ts": "2026-08-03T00:00:00Z",
            },
            state_dir=tmp_path,
        )
    assert not game_data_path("test-world", state_dir=tmp_path).exists()


def test_ship_row_to_spec_bridge():
    data = load_game_data(FIXTURE)
    spec = ship_row_to_spec(data.ships[0])
    assert spec.name == "Fixture Scout"
    assert spec.holds == data.ships[0].max_holds
    assert spec.cost == data.ships[0].base_cost_credits
    assert spec.turns_per_warp == data.ships[0].turns_per_warp
    assert spec.fighters == data.ships[0].max_fighters
    assert spec.shields == data.ships[0].max_shields
