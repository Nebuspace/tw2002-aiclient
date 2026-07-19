"""TW-14 Map-fill / frontier explore planner tests."""

from pathlib import Path

from twclient import world_model
from twclient.explore import (
    frontier_edges,
    path_to_sector,
    plan_map_fill,
    plan_find_stardock,
    find_landmark_sectors,
)
import random


def _seed(world_id: str, state_dir: Path, records: list[dict]):
    world_model.bulk_upsert(world_id, records, state_dir=state_dir)


def test_frontier_finds_unmapped_neighbor(tmp_path: Path):
    wid = "test+mapfill"
    # 1→2 known; 2→99 unknown
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 99], "landmarks": []},
        ],
    )
    plan = plan_map_fill(
        wid, current_sector=1, turn_budget=10, epsilon=0.0, state_dir=tmp_path,
        rng=random.Random(0),
    )
    assert plan.known_sectors == 2
    assert plan.unmapped_targets == 1
    assert plan.next_hop is not None
    assert plan.next_hop.frm == 2
    assert plan.next_hop.to == 99
    assert plan.mode == "exploit"


def test_exhausted_when_fully_mapped(tmp_path: Path):
    wid = "test+full"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1], "landmarks": []},
        ],
    )
    plan = plan_map_fill(
        wid, current_sector=1, turn_budget=5, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.next_hop is None
    assert plan.mode == "exhausted"
    assert plan.unmapped_targets == 0


def test_zero_budget_exhausts_even_with_frontier(tmp_path: Path):
    wid = "test+budget"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [7], "landmarks": []},
        ],
    )
    plan = plan_map_fill(
        wid, current_sector=1, turn_budget=0, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.mode == "exhausted"
    assert plan.next_hop is None
    assert plan.unmapped_targets == 1


def test_epsilon_can_pick_deeper_edge(tmp_path: Path):
    wid = "test+eps"
    # From 1: edge to 50 (depth 1 via... actually 1→2→50 unknown from 2,
    # and 1→99 unknown direct depth 1). Two depth-1 edges; epsilon explore
    # just needs non-None pick.
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2, 99], "landmarks": []},
            {"sector_id": 2, "warps": [1, 50], "landmarks": []},
        ],
    )
    plan = plan_map_fill(
        wid, current_sector=1, turn_budget=3, epsilon=1.0, state_dir=tmp_path,
        rng=random.Random(1),
    )
    assert plan.mode == "explore"
    assert plan.next_hop is not None
    assert plan.next_hop.to in (99, 50)


def test_find_stardock_landmark(tmp_path: Path):
    wid = "test+sd"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 10, "warps": [11], "landmarks": ["FedSpace"]},
            {"sector_id": 11, "warps": [10], "landmarks": ["StarDock"]},
        ],
    )
    assert find_landmark_sectors(wid, "stardock", state_dir=tmp_path) == [11]


def test_path_to_sector():
    graph = {1: (2,), 2: (1, 3), 3: (2,)}
    assert path_to_sector(graph, 1, 3) == (1, 2, 3)
    assert path_to_sector(graph, 1, 1) == (1,)
    assert path_to_sector(graph, 1, 9) is None


def test_frontier_edges_unit():
    graph = {1: (2,), 2: (1, 9)}
    edges = frontier_edges(graph, start=1)
    assert len(edges) == 1
    assert edges[0].frm == 2 and edges[0].to == 9


def test_find_stardock_routes_when_landmark_known(tmp_path: Path):
    wid = "test+sdroute"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3], "landmarks": []},
            {"sector_id": 3, "warps": [2], "landmarks": ["StarDock"]},
        ],
    )
    plan = plan_find_stardock(
        wid, current_sector=1, turn_budget=5, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.found is True
    assert plan.mode == "route"
    assert plan.route == (1, 2, 3)
    assert plan.next_sector == 2
    assert plan.hunt is None


def test_find_stardock_arrived(tmp_path: Path):
    wid = "test+sdhere"
    _seed(
        wid,
        tmp_path,
        [{"sector_id": 7, "warps": [], "landmarks": ["StarDock"]}],
    )
    plan = plan_find_stardock(
        wid, current_sector=7, turn_budget=3, state_dir=tmp_path,
    )
    assert plan.mode == "arrived"
    assert plan.next_sector is None
    assert plan.route == (7,)


def test_find_stardock_hunts_via_map_fill(tmp_path: Path):
    wid = "test+sdhunt"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 99], "landmarks": []},
        ],
    )
    plan = plan_find_stardock(
        wid, current_sector=1, turn_budget=4, epsilon=0.0, state_dir=tmp_path,
        rng=random.Random(0),
    )
    assert plan.found is False
    assert plan.mode == "hunt"
    assert plan.next_sector == 99
    assert plan.hunt is not None
    assert plan.hunt.next_hop is not None
    assert plan.hunt.next_hop.to == 99
