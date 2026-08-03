"""WO-FORMATIONS-CATALOG-PORT — in-tree catalog + planner seam."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tw2002_aiclient import formations, world_model
from tw2002_aiclient.explore import (
    INTENT_FIND_FORMATIONS,
    INTENTS,
    ARMABLE_INTENTS,
    plan_find_formations,
    warp_target_for_intent,
)


WORLD = "w-form"


def test_no_twclient_import_in_formations_module():
    src = Path(formations.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("twclient")
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("twclient")


def test_catalog_world_finds_dead_ends(tmp_path: Path):
    world_model.upsert_sector(
        WORLD, {"sector_id": 10, "warps": [11]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        WORLD, {"sector_id": 11, "warps": [10, 12]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        WORLD, {"sector_id": 12, "warps": [11]}, state_dir=tmp_path
    )
    cat = formations.catalog_world(WORLD, state_dir=tmp_path)
    cands = cat.genesis_candidates
    assert {c.sectors[0] for c in cands} == {10, 12}
    assert all(c.kind == "dead_end" for c in cands)


def test_plan_find_formations_unavailable_without_provider(tmp_path: Path):
    plan = plan_find_formations(
        WORLD, current_sector=1, turn_budget=5, state_dir=tmp_path
    )
    assert plan.mode == "unavailable"


def test_plan_find_formations_uses_real_catalog(tmp_path: Path):
    world_model.upsert_sector(
        WORLD, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        WORLD, {"sector_id": 2, "warps": [1]}, state_dir=tmp_path
    )
    plan = plan_find_formations(
        WORLD,
        current_sector=1,
        turn_budget=5,
        state_dir=tmp_path,
        catalog_provider=formations.catalog_world,
    )
    assert plan.mode == "arrived"
    assert plan.found is True


def test_intent_find_formations_in_intents_not_armable():
    assert INTENT_FIND_FORMATIONS in INTENTS
    assert INTENT_FIND_FORMATIONS not in ARMABLE_INTENTS
    assert ARMABLE_INTENTS == ("map_fill", "find_stardock")


def test_warp_target_routes_formations_intent(tmp_path: Path):
    world_model.upsert_sector(
        WORLD, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        WORLD, {"sector_id": 2, "warps": [1, 3, 5]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        WORLD, {"sector_id": 3, "warps": [2]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        WORLD, {"sector_id": 5, "warps": [2]}, state_dir=tmp_path
    )
    # Planner routes to the dead-end's entrance; from the spur, hop toward it.
    tick = warp_target_for_intent(
        INTENT_FIND_FORMATIONS,
        WORLD,
        current_sector=5,
        turn_budget=10,
        state_dir=tmp_path,
    )
    assert tick.next_sector == 2
    assert tick.goal_reached is False
    # Standing on the entrance of a catalogued dead-end → arrived.
    arrived = warp_target_for_intent(
        INTENT_FIND_FORMATIONS,
        WORLD,
        current_sector=2,
        turn_budget=10,
        state_dir=tmp_path,
    )
    assert arrived.goal_reached is True
    assert arrived.next_sector is None


def test_formations_from_sectors_abort_vs_empty():
    assert formations.formations_from_sectors(None) is None
    assert formations.formations_from_sectors("nope") is None
    assert formations.formations_from_sectors([{"sector_id": 1, "warps": [2]}, "x"]) is None
    empty = formations.formations_from_sectors([])
    assert empty is not None
    assert empty.formations == []
    assert empty.genesis_candidates == []


def test_panel_items_from_catalog_dead_end_shape():
    cat = formations.FormationsCatalog(
        [
            formations.Formation(
                kind="dead_end", sectors=(7,), entrance=8, detail="one warp → 8"
            )
        ]
    )
    items = formations.panel_items_from_catalog(cat)
    assert items == [
        {
            "name": "Dead-end #7",
            "blurb": "one warp — defensible siting candidate",
        }
    ]


def test_catalog_world_maps_abort_to_empty(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("store down")

    monkeypatch.setattr(world_model, "all_sectors", boom)
    cat = formations.catalog_world(WORLD)
    assert cat.formations == []
