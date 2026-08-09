"""WO-BUILD-CHAIN-HUNT-SIBLING-EXHAUST-EXPLORE — sibling-exhaust planner tests."""

from __future__ import annotations

from pathlib import Path

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import (
    INTENT_CHAIN_HUNT,
    INTENTS,
    ARMABLE_INTENTS,
    ChainHuntState,
    densest_reachable_sector,
    known_graph,
    plan_chain_hunt,
    plan_exhausted_recovery,
    warp_target_for_intent,
)


def _seed(world_id: str, state_dir: Path, records: list[dict]) -> None:
    world_model.bulk_upsert(world_id, records, state_dir=state_dir)


def test_chain_hunt_in_intents_not_play_armable():
    assert INTENT_CHAIN_HUNT in INTENTS
    assert INTENT_CHAIN_HUNT not in ARMABLE_INTENTS


def test_visit_unmapped_sibling_then_return(tmp_path: Path):
    """Canon steps 1–3: at port 5 with unmapped 6/7/8, visit lowest id, then return."""
    wid = "test+chain-hunt-sib"
    _seed(
        wid,
        tmp_path,
        [
            {
                "sector_id": 5,
                "warps": [6, 7, 8],
                "port": {"class": "BBS"},
                "landmarks": [],
            },
        ],
    )
    plan = plan_chain_hunt(
        wid,
        current_sector=5,
        turn_budget=20,
        exhaust_depth=3,
        state_dir=tmp_path,
    )
    assert plan.mode == "visit_sibling"
    assert plan.next_sector == 6
    assert plan.state.anchor == 5
    assert plan.state.visiting == 6

    # Simulate flyby: sector 6 mapped, no port.
    _seed(
        wid,
        tmp_path,
        [
            {
                "sector_id": 5,
                "warps": [6, 7, 8],
                "port": {"class": "BBS"},
                "landmarks": [],
            },
            {"sector_id": 6, "warps": [5], "landmarks": []},
        ],
    )
    plan2 = plan_chain_hunt(
        wid,
        current_sector=6,
        turn_budget=19,
        exhaust_depth=3,
        state=plan.state,
        state_dir=tmp_path,
    )
    assert plan2.mode == "return_anchor"
    assert plan2.next_sector == 5
    assert plan2.state.return_to == 5


def test_no_port_closes_branch_then_next_sibling(tmp_path: Path):
    wid = "test+chain-hunt-close"
    _seed(
        wid,
        tmp_path,
        [
            {
                "sector_id": 5,
                "warps": [6, 7],
                "port": {"class": "BBS"},
                "landmarks": [],
            },
            {"sector_id": 6, "warps": [5], "landmarks": []},
        ],
    )
    st = ChainHuntState(anchor=5, visiting=None, return_to=None)
    # At anchor after return from 6 — next sibling is 7.
    plan = plan_chain_hunt(
        wid,
        current_sector=5,
        turn_budget=10,
        exhaust_depth=3,
        state=st,
        state_dir=tmp_path,
    )
    assert plan.mode == "visit_sibling"
    assert plan.next_sector == 7


def test_port_sibling_reanchors(tmp_path: Path):
    wid = "test+chain-hunt-reanchor"
    _seed(
        wid,
        tmp_path,
        [
            {
                "sector_id": 5,
                "warps": [6],
                "port": {"class": "BBS"},
                "landmarks": [],
            },
            {
                "sector_id": 6,
                "warps": [5, 9],
                "port": {"class": "SSS"},
                "landmarks": [],
            },
        ],
    )
    st = ChainHuntState(anchor=5, visiting=6)
    plan = plan_chain_hunt(
        wid,
        current_sector=6,
        turn_budget=10,
        exhaust_depth=3,
        state=st,
        state_dir=tmp_path,
    )
    assert plan.state.anchor == 6
    assert plan.state.ancestors == (5,)
    # New anchor's closed set includes unmapped 9.
    assert plan.mode == "visit_sibling"
    assert plan.next_sector == 9


def test_backtrack_to_ancestor_with_open_siblings(tmp_path: Path):
    """Exhausted child port backtracks to ancestor that still has open siblings."""
    wid = "test+chain-hunt-backtrack"
    _seed(
        wid,
        tmp_path,
        [
            {
                "sector_id": 5,
                "warps": [6, 7],
                "port": {"class": "BBS"},
                "landmarks": [],
            },
            {
                "sector_id": 6,
                "warps": [5],
                "port": {"class": "SSS"},
                "landmarks": [],
            },
            # 7 still unmapped from 5
        ],
    )
    st = ChainHuntState(ancestors=(5,), anchor=6, visiting=None)
    plan = plan_chain_hunt(
        wid,
        current_sector=6,
        turn_budget=10,
        exhaust_depth=3,
        state=st,
        state_dir=tmp_path,
    )
    assert plan.mode == "backtrack"
    assert plan.next_sector == 5
    assert plan.state.anchor == 5
    assert plan.state.ancestors == ()


def test_never_densest_recovery_while_ancestor_has_open_siblings(tmp_path: Path):
    """Critical regression: densest/Map-fill recovery must not win over backtrack."""
    wid = "test+chain-hunt-no-densest"
    # Graph: port 5→6(port,exhausted),5→7(unmapped). Also a dense dead-end 1.
    _seed(
        wid,
        tmp_path,
        [
            {
                "sector_id": 5,
                "warps": [6, 7, 1],
                "port": {"class": "BBS"},
                "landmarks": [],
            },
            {
                "sector_id": 6,
                "warps": [5],
                "port": {"class": "SSS"},
                "landmarks": [],
            },
            {
                "sector_id": 1,
                "warps": [5, 2, 3, 4],
                "landmarks": [],
            },
            {"sector_id": 2, "warps": [1], "landmarks": []},
            {"sector_id": 3, "warps": [1], "landmarks": []},
            {"sector_id": 4, "warps": [1], "landmarks": []},
        ],
    )
    graph = known_graph(wid, state_dir=tmp_path)
    densest = densest_reachable_sector(graph, 6, world_id=wid, state_dir=tmp_path)
    assert densest == 1  # densest would prefer sector 1

    recovery = plan_exhausted_recovery(
        wid, current_sector=6, turn_budget=10, state_dir=tmp_path
    )
    assert recovery.policy == "densest"
    assert recovery.next_sector is not None

    st = ChainHuntState(ancestors=(5,), anchor=6)
    plan = plan_chain_hunt(
        wid,
        current_sector=6,
        turn_budget=10,
        exhaust_depth=3,
        state=st,
        state_dir=tmp_path,
    )
    assert plan.mode == "backtrack"
    assert plan.next_sector == 5
    # Map-fill recovery would chase densest *target* 1; Chain-hunt must resume
    # the ancestor port (5) instead — even if the immediate hop coincides.
    assert recovery.target_sector == 1
    assert plan.state.anchor == 5
    assert plan.mode != f"recovery:{recovery.policy}"
    assert "densest" not in plan.mode
    assert "last_resort" not in plan.mode


def test_missing_exhaust_depth_fail_closed(tmp_path: Path):
    wid = "test+chain-hunt-depth"
    _seed(
        wid,
        tmp_path,
        [{"sector_id": 1, "warps": [2], "port": {"class": "BBS"}, "landmarks": []}],
    )
    tick = warp_target_for_intent(
        INTENT_CHAIN_HUNT,
        wid,
        current_sector=1,
        turn_budget=10,
        state_dir=tmp_path,
        exhaust_depth=None,
    )
    assert tick.next_sector is None
    assert "missing_exhaust_depth" in tick.reason


def test_invalid_exhaust_depth_rejected(tmp_path: Path):
    wid = "test+chain-hunt-bad-depth"
    _seed(
        wid,
        tmp_path,
        [{"sector_id": 1, "warps": [2], "port": {"class": "BBS"}, "landmarks": []}],
    )
    plan = plan_chain_hunt(
        wid,
        current_sector=1,
        turn_budget=10,
        exhaust_depth=0,
        state_dir=tmp_path,
    )
    assert plan.next_sector is None
    assert "invalid_exhaust_depth" in plan.reason
