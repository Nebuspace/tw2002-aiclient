"""Pins for WO-AUDIT-BUILD-SHIPPROG-FOCUS-OVERLAY — game_data → status merge."""

from __future__ import annotations

from tw2002_aiclient.game_data import (
    CargoHoldRow,
    GameData,
    ShipRow,
    game_data_path,
    save_world_game_data,
)
from tw2002_aiclient.game_data_stats import GameDataStats


def _ship(name: str, cost: int) -> ShipRow:
    return ShipRow(
        ship_name=name,
        max_holds=40,
        max_fighters=10,
        max_shields=0,
        combat_odds_modifier=1.0,
        turns_per_warp=3,
        base_cost_credits=cost,
        alignment_requirement=None,
        rank_requirement=None,
        transwarp_capable=False,
        special_abilities=(),
        source="introspected:test",
        last_verified_ts="2026-08-04T00:00:00Z",
    )


def test_game_data_stats_merge_ship_and_hold(tmp_path):
    wid = "overlay-world"
    data = GameData(
        world_id=wid,
        ships=(_ship("Merchant Cruiser", 36750), _ship("Scout", 0)),
        cargo_holds=(
            CargoHoldRow(
                cost_per_hold=1200,
                source="introspected:test",
                last_verified_ts="2026-08-04T00:00:00Z",
            ),
        ),
    )
    save_world_game_data(data, state_dir=tmp_path)
    assert game_data_path(wid, state_dir=tmp_path).is_file()

    gds = GameDataStats()
    gds.refresh(wid, state_dir=tmp_path)
    merged = gds.merge({})
    assert merged["ship_prices_count"] == 1
    assert merged["hold_price_label"] == "1,200cr"


def test_game_data_stats_zero_ships_emits_count(tmp_path):
    wid = "empty-catalog"
    save_world_game_data(GameData(world_id=wid), state_dir=tmp_path)
    gds = GameDataStats()
    gds.refresh(wid, state_dir=tmp_path)
    merged = gds.merge({})
    assert merged["ship_prices_count"] == 0
    assert "hold_price_label" not in merged


def test_game_data_stats_does_not_clobber():
    gds = GameDataStats()
    gds._ships_seen = True
    gds._ship_prices_count = 9
    gds._hold_seen = True
    gds._hold_price_label = "99cr"
    prior = {"ship_prices_count": 4, "hold_price_label": "1,200cr"}
    merged = gds.merge(prior)
    assert merged["ship_prices_count"] == 4
    assert merged["hold_price_label"] == "1,200cr"
