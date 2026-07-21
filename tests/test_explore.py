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
    """HIGH fix (mack/cipher adversarial re-verify, 2026-07-21): the
    nearest frontier edge (1→2 known, 2→99 unknown) is found FROM sector
    2, not from the current sector 1 -- `next_sector` must be the valid
    ADJACENT hop toward it (2, the only sector 1 can actually warp to
    right now), never the frontier's own far-side target (99) directly.
    `hunt.next_hop.to` still reports the RAW frontier target (99) --
    that field is informational/display only, unaffected by this fix
    (see `_adjacent_hop_toward`'s own docstring)."""
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
    assert plan.next_sector == 2  # adjacent hop toward the frontier, NOT the far-side target 99
    assert plan.hunt is not None
    assert plan.hunt.next_hop is not None
    assert plan.hunt.next_hop.to == 99


def test_find_stardock_hunt_resolves_a_multi_hop_frontier_to_the_first_adjacent_step(tmp_path: Path):
    """mack's exact repro: sector 1 warps to {2, 3} (both already
    mapped), sector 3 warps to 99 (unmapped) -- the nearest/only
    frontier edge is found FROM sector 3, two known hops from current
    sector 1. The OLD code fired a bare warp straight at 99 (invalid --
    not adjacent to 1 at all, the game would reject it and the loop
    would spin toward max_ticks with zero progress). The fix must
    resolve this to the FIRST hop of the known path toward 3 -- i.e. 3
    itself, which genuinely IS one of sector 1's own listed warps."""
    wid = "test+sdhunt-multihop"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2, 3], "landmarks": []},
            {"sector_id": 2, "warps": [1], "landmarks": []},
            {"sector_id": 3, "warps": [99], "landmarks": []},
        ],
    )
    plan = plan_find_stardock(
        wid, current_sector=1, turn_budget=4, epsilon=0.0, state_dir=tmp_path,
        rng=random.Random(0),
    )
    assert plan.found is False
    assert plan.mode == "hunt"
    assert plan.next_sector == 3  # adjacent (in sector 1's own warps), toward frm=3
    assert plan.hunt.next_hop.frm == 3
    assert plan.hunt.next_hop.to == 99


def test_find_formations_routes_to_dead_end(tmp_path: Path):
    from twclient.explore import plan_find_formations

    wid = "test+form"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3], "landmarks": []},
            {"sector_id": 3, "warps": [2], "landmarks": []},  # dead-end
        ],
    )
    plan = plan_find_formations(
        wid, current_sector=1, turn_budget=5, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.found is True
    assert plan.mode == "route"
    assert plan.next_sector == 2
    assert plan.kind == "dead-end"


def test_cycle_explore_mode_and_decision_lines():
    from twclient.explore import (
        cycle_explore_mode,
        format_explore_decision_lines,
        MapFillPlan,
        FrontierEdge,
    )

    assert cycle_explore_mode("off") == "mapfill"
    assert cycle_explore_mode("formations") == "off"
    plan = MapFillPlan(
        next_hop=FrontierEdge(frm=1, to=9, depth=1),
        frontier=(FrontierEdge(frm=1, to=9, depth=1),),
        known_sectors=2,
        unmapped_targets=1,
        turns_budget_remaining=3,
        mode="exploit",
    )
    lines = format_explore_decision_lines("mapfill", plan)
    assert lines[0] == "MAP-FILL"
    assert "→9" in lines[1]


def test_plan_map_fill_prefers_port_neighborhood_over_nearer_unrelated(tmp_path: Path):
    """Accept-2 WO-PORT-CHAIN-SEED: seeded port fringe beats a depth-1 unrelated hop."""
    wid = "test+portseed"
    _seed(
        wid,
        tmp_path,
        [
            # current at 1: direct unmapped 99 (depth 1, no port)
            {"sector_id": 1, "warps": [10, 99], "landmarks": []},
            # known port at 10 with unmapped neighbor 11 (depth 2 from start)
            {"sector_id": 10, "warps": [1, 11], "port": {"class": "BSB"}, "landmarks": []},
        ],
    )
    plan = plan_map_fill(
        wid, current_sector=1, turn_budget=10, epsilon=0.0, state_dir=tmp_path,
        rng=random.Random(0),
    )
    assert plan.next_hop is not None
    assert plan.next_hop.frm == 10
    assert plan.next_hop.to == 11
    assert plan.mode == "exploit"


def test_plan_map_fill_falls_back_to_nearest_when_no_port_seeds(tmp_path: Path):
    wid = "test+noports"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2, 99], "landmarks": []},
            {"sector_id": 2, "warps": [1, 50], "landmarks": []},
        ],
    )
    plan = plan_map_fill(
        wid, current_sector=1, turn_budget=10, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.next_hop is not None
    # nearest depth-1 edges: 1→99 (and 2→50 is depth 2) — exploit picks depth-sorted first
    assert plan.next_hop.to in (99, 50)
    assert plan.next_hop.depth == 1
