"""WO-AUDIT-BUILD-SECTOR-THREAT-FIGHTERS-GUARD-INPUT — mines/fighters STOP."""

from __future__ import annotations

from pathlib import Path

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import map_fill_warp_target
from tw2002_aiclient.formations import route_hazard_for_hop, threat_hazard_for_sector
from tw2002_aiclient import trade_adapter


def test_threat_hazard_mines_and_fighters():
    assert threat_hazard_for_sector(7, {"mines": True, "fighters": None}) == (
        "route_hazard:mines:7"
    )
    assert threat_hazard_for_sector(8, {"mines": False, "fighters": 12}) == (
        "route_hazard:fighters:8"
    )
    assert threat_hazard_for_sector(
        9, {"mines": False, "fighters": {"count": 3, "owner": "NPC"}}
    ) == "route_hazard:fighters:9"
    assert threat_hazard_for_sector(10, {"mines": False, "fighters": None}) is None
    assert threat_hazard_for_sector(11, {"mines": False, "fighters": 0}) is None


def test_route_hazard_for_hop_checks_destination_threats():
    graph = {1: (2,), 2: (1,)}
    assert route_hazard_for_hop(graph, 1, 2) is None
    assert (
        route_hazard_for_hop(
            graph,
            1,
            2,
            threats_by_sector={2: {"mines": True, "fighters": None}},
        )
        == "route_hazard:mines:2"
    )
    assert (
        route_hazard_for_hop(
            graph,
            1,
            2,
            threats_by_sector={2: {"mines": False, "fighters": 5}},
        )
        == "route_hazard:fighters:2"
    )


def test_map_fill_halts_on_fighter_destination(tmp_path: Path):
    wid = "test+threat-fighters"
    world_model.bulk_upsert(
        wid,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {
                "sector_id": 2,
                "warps": [1, 99],
                "landmarks": [],
                "threats": {"mines": False, "fighters": 4},
            },
        ],
        state_dir=tmp_path,
    )
    target, reason = map_fill_warp_target(
        wid,
        current_sector=1,
        turn_budget=10,
        state_dir=tmp_path,
        rng=__import__("random").Random(0),
    )
    assert target is None
    assert reason == "route_hazard:fighters:2"


def test_build_trade_hops_excludes_fighter_shortest_path(tmp_path: Path):
    wid = "w-threat-fighters"
    clock = __import__("datetime").datetime(
        2026, 7, 20, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc
    )

    def upsert(sector_id, *, warps, commodities=None, threats=None):
        record = {"sector_id": sector_id, "warps": list(warps)}
        if commodities is not None:
            record["port"] = {
                "commodities": commodities,
                "last_seen_ts": world_model._now_iso(lambda: clock),
            }
        if threats is not None:
            record["threats"] = threats
        world_model.upsert_sector(wid, record, state_dir=tmp_path, now=lambda: clock)

    row = lambda name, status, pct: {
        "name": name,
        "status": status,
        "amount": 1000,
        "pct": pct,
    }
    upsert(
        1,
        warps=(2,),
        commodities=[row("Equipment", "selling", 100)],
    )
    upsert(
        2,
        warps=(1, 3),
        threats={"mines": False, "fighters": 9},
    )
    upsert(
        3,
        warps=(2,),
        commodities=[row("Equipment", "buying", 0)],
    )
    hops, _note = trade_adapter.build_trade_hops(
        wid,
        state_dir=tmp_path,
        now=lambda: clock,
        config=trade_adapter.TradeAdapterConfig(max_hops=20, max_route_searches=20),
    )
    assert all(not (h.frm == 1 and h.to == 3) for h in hops)
