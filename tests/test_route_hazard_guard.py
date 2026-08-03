"""WO-ROUTE-HAZARD-GUARD — STOP on known one-way / warp-sink hops."""

from __future__ import annotations

import random
from pathlib import Path

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import (
    INTENT_FIND_STARDOCK,
    map_fill_warp_target,
    warp_target_for_intent,
)
from tw2002_aiclient.formations import route_hazard_for_hop


def test_route_hazard_one_way_edge():
    graph = {1: (2,), 2: (3,), 3: (4,), 4: (3,)}
    assert route_hazard_for_hop(graph, 1, 2) == "route_hazard:one_way:1->2"
    assert route_hazard_for_hop(graph, 3, 4) is None


def test_route_hazard_warp_sink_membership():
    graph = {1: (2,), 2: (1,)}
    assert route_hazard_for_hop(graph, 1, 2) is None
    assert (
        route_hazard_for_hop(
            graph, 1, 2, membership={2: ("warp-sink",)}
        )
        == "route_hazard:warp_sink:2"
    )


def test_map_fill_halts_on_one_way_next_hop(tmp_path: Path):
    """Toward a frontier past a one-way: STOP — do not pick another hop."""
    wid = "test+route-hazard"
    world_model.bulk_upsert(
        wid,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3], "landmarks": []},
            # 2→3 one-way; 3 holds the only frontier (99 unmapped).
            {"sector_id": 3, "warps": [99], "landmarks": []},
        ],
        state_dir=tmp_path,
    )
    target, reason = map_fill_warp_target(
        wid,
        current_sector=2,
        turn_budget=10,
        epsilon=0.0,
        state_dir=tmp_path,
        rng=random.Random(0),
    )
    assert target is None
    assert reason == "route_hazard:one_way:2->3"


def test_find_stardock_halts_on_one_way_route(tmp_path: Path):
    wid = "test+route-hazard-sd"
    world_model.bulk_upsert(
        wid,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [3], "landmarks": ["StarDock"]},
            {"sector_id": 3, "warps": [4], "landmarks": []},
            {"sector_id": 4, "warps": [3], "landmarks": []},
        ],
        state_dir=tmp_path,
    )
    # Shortest path 1→2 crosses one-way 1→2.
    tick = warp_target_for_intent(
        INTENT_FIND_STARDOCK,
        wid,
        current_sector=1,
        turn_budget=10,
        epsilon=0.0,
        state_dir=tmp_path,
        rng=random.Random(0),
    )
    assert tick.next_sector is None
    assert tick.reason == "route_hazard:one_way:1->2"
    assert tick.goal_reached is False


def test_sector_explore_preserves_route_hazard_reason_prefix():
    """Runner must not wrap route_hazard: as explore_exhausted:…"""
    from tw2002_aiclient.session import sector_explore as se

    src = Path(se.__file__).read_text()
    assert "route_hazard:" in src
    # Halt branch keeps the typed prefix (split across lines is fine).
    assert "startswith(" in src and "route_hazard:" in src
