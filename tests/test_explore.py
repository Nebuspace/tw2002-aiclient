"""TW-14 Map-fill / frontier explore planner tests."""

from pathlib import Path

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import (
    frontier_edges,
    path_to_sector,
    plan_map_fill,
    plan_find_stardock,
    find_landmark_sectors,
)
import random

import pytest


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


class _FakeFormation:
    """Minimal stand-in for a TW-16 catalogue entry: only the three
    attributes `plan_find_formations` actually reads."""

    def __init__(self, kind, sectors, entrance=None):
        self.kind = kind
        self.sectors = sectors
        self.entrance = entrance


def _fake_catalog(*formations):
    """A `catalog_provider` seam double. Deliberately NOT a port of the
    deleted `twclient.formations` — it exposes only `.genesis_candidates`,
    which is the whole contract `plan_find_formations` depends on."""

    class _Cat:
        genesis_candidates = list(formations)

    return lambda world_id, *, state_dir=None: _Cat()


def test_find_formations_routes_to_dead_end(tmp_path: Path):
    """WO-EXPLORE-TWCLIENT-FORMATIONS-LANDMINE: previously an unconditional
    `pytest.skip("formations catalog not ported yet")`. The reason for the
    skip was that the only catalogue source was the DELETED
    `twclient.formations` — the same import that made this function raise
    `ModuleNotFoundError` on first call. The `catalog_provider` seam removes
    both problems at once, so this test now RUNS against the real routing
    algorithm instead of documenting an intention."""
    from tw2002_aiclient.explore import plan_find_formations

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
        wid,
        current_sector=1,
        turn_budget=5,
        epsilon=0.0,
        state_dir=tmp_path,
        catalog_provider=_fake_catalog(_FakeFormation("dead-end", (3,), entrance=3)),
    )
    assert plan.found is True
    assert plan.mode == "route"
    assert plan.next_sector == 2
    assert plan.kind == "dead-end"


def test_find_formations_without_a_provider_refuses_honestly(tmp_path: Path):
    """The landmine pin. With no catalogue seam wired, this must return a
    TYPED refusal — never raise, and never borrow a mode that makes a claim
    about the world.

    `"hunt"`/`"exhausted"` would both assert something the code cannot know:
    that a catalogue was consulted and held nothing. Only `"unavailable"`
    says the true thing — no catalogue was reachable. Before this WO the
    same call raised `ModuleNotFoundError: No module named 'twclient'`."""
    from tw2002_aiclient.explore import plan_find_formations

    wid = "test+form-noprovider"
    _seed(wid, tmp_path, [{"sector_id": 1, "warps": [2], "landmarks": []}])

    plan = plan_find_formations(
        wid, current_sector=1, turn_budget=5, epsilon=0.0, state_dir=tmp_path
    )

    assert plan.mode == "unavailable"
    # The load-bearing half: not merely "some falsy plan", but specifically
    # NOT a mode that would read downstream as a surveyed-and-empty world.
    assert plan.mode not in ("hunt", "exhausted", "catalog", "route", "arrived")
    assert plan.found is False
    assert plan.hunt is None
    assert plan.route is None
    assert plan.next_sector is None
    assert plan.targets == ()


def test_cycle_explore_mode_and_decision_lines():
    from tw2002_aiclient.explore import (
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


def test_exhausted_recovery_warps_toward_densest_hub(tmp_path: Path):
    """WO-EXPLORE-NO-CANDIDATES: fully mapped component → densest hop."""
    from tw2002_aiclient.explore import plan_exhausted_recovery, plan_find_stardock

    wid = "test+densest"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3, 4], "landmarks": []},  # densest
            {"sector_id": 3, "warps": [2], "landmarks": []},
            {"sector_id": 4, "warps": [2], "landmarks": []},
        ],
    )
    recovery = plan_exhausted_recovery(
        wid, current_sector=1, turn_budget=5, state_dir=tmp_path,
    )
    assert recovery.policy == "densest"
    assert recovery.target_sector == 2
    assert recovery.next_sector == 2

    plan = plan_find_stardock(
        wid, current_sector=1, turn_budget=5, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.mode == "recovery:densest"
    assert plan.next_sector == 2


def test_exhausted_recovery_prefers_stardock_when_landmark_known(tmp_path: Path):
    from tw2002_aiclient.explore import plan_exhausted_recovery

    wid = "test+recov-sd"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3, 9], "landmarks": []},  # denser than path to SD
            {"sector_id": 3, "warps": [2], "landmarks": ["StarDock"]},
            {"sector_id": 9, "warps": [2], "landmarks": []},
        ],
    )
    recovery = plan_exhausted_recovery(
        wid, current_sector=1, turn_budget=5, state_dir=tmp_path,
    )
    assert recovery.policy == "stardock"
    assert recovery.target_sector == 3
    assert recovery.next_sector == 2


def test_exhausted_recovery_halts_when_already_at_densest(tmp_path: Path):
    from tw2002_aiclient.explore import plan_exhausted_recovery, plan_find_stardock

    wid = "test+at-densest"
    _seed(
        wid,
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3, 4], "landmarks": []},
            {"sector_id": 3, "warps": [2], "landmarks": []},
            {"sector_id": 4, "warps": [2], "landmarks": []},
        ],
    )
    recovery = plan_exhausted_recovery(
        wid, current_sector=2, turn_budget=5, state_dir=tmp_path,
    )
    assert recovery.policy == "halt"
    assert recovery.next_sector is None
    assert recovery.reason.startswith("explore_exhausted:")

    plan = plan_find_stardock(
        wid, current_sector=2, turn_budget=5, epsilon=0.0, state_dir=tmp_path,
    )
    assert plan.mode == "exhausted"
    assert plan.next_sector is None
