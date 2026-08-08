"""Pins for WO-WIRE-SHIP-SPEC-CATALOG-INTO-UPGRADE-DECISIONS."""

from __future__ import annotations

from tw2002_aiclient.chains import ProfitChain, TradeHop
from tw2002_aiclient.cockpit.decisions import compose_decisions_lines
from tw2002_aiclient.game_data import (
    CargoHoldRow,
    GameData,
    ShipRow,
    save_world_game_data,
)
from tw2002_aiclient.game_data_stats import GameDataStats
from tw2002_aiclient.ship_upgrade_decision import (
    merge_upgrade_status_inputs,
    ship_spec_from_current_info,
    upgrade_catalog_from_ships,
    upgrade_decision_from_status,
    upgrade_loop_from_chain,
    upgrade_player_from_status,
)


def _ship(name: str, *, cost: int, holds: int = 75, warp: int = 3) -> ShipRow:
    return ShipRow(
        ship_name=name,
        max_holds=holds,
        max_fighters=100,
        max_shields=50,
        combat_odds_modifier=1.0,
        turns_per_warp=warp,
        base_cost_credits=cost,
        alignment_requirement=0,
        rank_requirement=None,
        transwarp_capable=False,
        special_abilities=(),
        source="introspected:test",
        last_verified_ts="2026-08-08T00:00:00Z",
    )


def _long_chain(*, margin: float = 250.0, turns: int = 8) -> ProfitChain:
    hops = tuple(
        TradeHop(frm=i, to=i + 1, commodity="Fuel Ore", margin=margin / 4, turns=turns // 4)
        for i in range(1, 5)
    )
    # Force exact totals the loop helper reads.
    return ProfitChain(
        sectors=(1, 2, 3, 4, 5, 1),
        hops=hops,
        overall_profit=margin,
        turns=turns,
        cr_per_turn=margin / turns,
        cr_per_execution=margin,
    )


def test_upgrade_catalog_from_ships_priced_only():
    ships = (
        _ship("Merchant Cruiser", cost=50_000, holds=75),
        _ship("Freebie", cost=0, holds=20),
    )
    catalog = upgrade_catalog_from_ships(ships)
    assert len(catalog) == 1
    assert catalog[0]["name"] == "Merchant Cruiser"
    assert catalog[0]["cost"] == 50_000
    assert catalog[0]["holds"] == 75


def test_upgrade_player_calls_ship_spec_from_current_info():
    ships = (_ship("Dragon Quest", cost=99_000, holds=75),)
    status = {
        "turns_left": 800,
        "current_ship": {
            "ship_type": "4 Dragons Ltd Dragon Quest",
            "total_holds": 60,
            "fighters": 150,
            "turns_per_warp": 3,
        },
    }
    # Adapter match is the load-bearing call for this WO.
    assert ship_spec_from_current_info(status["current_ship"], catalog=ships) is not None
    player = upgrade_player_from_status(status, ships=ships)
    assert player is not None
    assert player["turns_left"] == 800
    assert player["current_holds"] == 60
    assert player["current_fighters"] == 150
    assert player["current_shields"] == 50  # catalog-only via ship_spec_from_current_info


def test_upgrade_loop_short_chain_caps_stock_at_current_holds():
    short = ProfitChain(
        sectors=(1, 2, 1),
        hops=(
            TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=100, turns=2),
            TradeHop(frm=2, to=1, commodity="Organics", margin=100, turns=2),
        ),
        overall_profit=200,
        turns=4,
        cr_per_turn=50.0,
        cr_per_execution=200,
    )
    loop = upgrade_loop_from_chain(short, current_holds=40, catalog_max_holds=200)
    assert loop is not None
    assert loop["stock_capacity"] == 40  # needs longer chain for bigger hulls


def test_upgrade_loop_long_chain_defers_stock_to_catalog_max():
    loop = upgrade_loop_from_chain(
        _long_chain(), current_holds=40, catalog_max_holds=200
    )
    assert loop is not None
    assert loop["margin_per_hold"] == 250
    assert loop["turns_per_cycle"] == 8
    assert loop["stock_capacity"] == 200


def test_game_data_stats_merges_upgrade_catalog_and_player(tmp_path):
    wid = "upgrade-wire-world"
    data = GameData(
        world_id=wid,
        ships=(
            _ship("Merchant Cruiser", cost=50_000, holds=75),
            _ship("Scout Marauder", cost=10_000, holds=40),
        ),
        cargo_holds=(
            CargoHoldRow(
                cost_per_hold=100,
                source="introspected:test",
                last_verified_ts="2026-08-08T00:00:00Z",
            ),
        ),
    )
    save_world_game_data(data, state_dir=tmp_path)
    gds = GameDataStats()
    gds.refresh(wid, state_dir=tmp_path)
    status = {
        "turns_left": 800,
        "current_ship": {
            "ship_type": "Scout Marauder",
            "total_holds": 40,
            "fighters": 10,
            "turns_per_warp": 3,
        },
    }
    merged = gds.merge(status)
    assert isinstance(merged.get("upgrade_catalog"), list)
    assert len(merged["upgrade_catalog"]) == 2
    assert merged.get("upgrade_cost_per_hold") == 100
    assert merged.get("upgrade_player") is not None
    assert merged["upgrade_player"]["current_holds"] == 40
    # Loop needs a priced chain — FocusScalars attaches that.
    assert "upgrade_loop" not in merged


def test_merge_with_chain_lights_upgrade_decision_and_decisions_panel():
    ships = (
        _ship("Merchant Cruiser", cost=50_000, holds=75),
        _ship("Scout Marauder", cost=10_000, holds=40),
    )
    base = {
        "turns_left": 800,
        "current_ship": {
            "ship_type": "Scout Marauder",
            "total_holds": 40,
            "fighters": 10,
            "turns_per_warp": 3,
        },
    }
    with_catalog = merge_upgrade_status_inputs(base, ships=ships, cost_per_hold=100)
    assert isinstance(with_catalog, dict)
    assert with_catalog.get("upgrade_catalog")
    assert with_catalog.get("upgrade_player")
    assert upgrade_decision_from_status(with_catalog) is None  # no loop yet

    full = merge_upgrade_status_inputs(with_catalog, chain=_long_chain())
    assert isinstance(full, dict)
    assert full.get("upgrade_loop") is not None
    decision = upgrade_decision_from_status(full)
    assert decision is not None
    assert decision.ship is not None or decision.recommend is False

    lines = compose_decisions_lines(full, width=60)
    assert any("Upgrade" in line for line in lines)


def test_upgrade_catalog_respects_player_alignment():
    ships = (
        ShipRow(
            ship_name="Merchant Cruiser",
            max_holds=75,
            max_fighters=100,
            max_shields=50,
            combat_odds_modifier=1.0,
            turns_per_warp=3,
            base_cost_credits=50_000,
            alignment_requirement=0,
            rank_requirement=None,
            transwarp_capable=False,
            special_abilities=(),
            source="introspected:test",
            last_verified_ts="2026-08-08T00:00:00Z",
        ),
        ShipRow(
            ship_name="Imperial Starship",
            max_holds=200,
            max_fighters=500,
            max_shields=200,
            combat_odds_modifier=1.2,
            turns_per_warp=2,
            base_cost_credits=500_000,
            alignment_requirement=1000,
            rank_requirement=None,
            transwarp_capable=False,
            special_abilities=(),
            source="introspected:test",
            last_verified_ts="2026-08-08T00:00:00Z",
        ),
    )
    # Without standing: omit-until-known → both commissioned True (prior default).
    raw = upgrade_catalog_from_ships(ships)
    assert {r["name"]: r["commissioned"] for r in raw} == {
        "Merchant Cruiser": True,
        "Imperial Starship": True,
    }
    gated = upgrade_catalog_from_ships(ships, player_alignment=2)
    by_name = {r["name"]: r["commissioned"] for r in gated}
    assert by_name["Merchant Cruiser"] is True
    assert by_name["Imperial Starship"] is False


def test_merge_upgrade_status_applies_alignment_to_catalog():
    ships = (
        ShipRow(
            ship_name="Imperial Starship",
            max_holds=200,
            max_fighters=500,
            max_shields=200,
            combat_odds_modifier=1.2,
            turns_per_warp=2,
            base_cost_credits=500_000,
            alignment_requirement=1000,
            rank_requirement=None,
            transwarp_capable=False,
            special_abilities=(),
            source="introspected:test",
            last_verified_ts="2026-08-08T00:00:00Z",
        ),
    )
    status = {
        "turns_left": 800,
        "alignment": 2,
        "current_ship": {
            "ship_type": "Imperial Starship",
            "total_holds": 40,
            "fighters": 10,
            "turns_per_warp": 2,
            "alignment": 2,
        },
    }
    merged = merge_upgrade_status_inputs(status, ships=ships, cost_per_hold=100)
    assert isinstance(merged, dict)
    cat = merged["upgrade_catalog"]
    assert len(cat) == 1
    assert cat[0]["commissioned"] is False
    assert merged["upgrade_player"]["alignment"] == 2
