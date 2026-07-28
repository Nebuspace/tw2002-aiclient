"""Formations planner tests — reborn seam (WO-TEST-FORMATIONS-REHAB).

Replaces the archive ``twclient.formations`` detector suite. The TW-16
catalogue package is gone (ADR-001); product coverage is
``explore.plan_find_formations`` + its ``catalog_provider`` seam (#142).
"""

from __future__ import annotations

import ast
from pathlib import Path

from tw2002_aiclient import explore, world_model

WORLD = "test+formations-rehab"


class _FakeFormation:
    def __init__(self, kind, sectors, entrance=None):
        self.kind = kind
        self.sectors = sectors
        self.entrance = entrance


def _fake_catalog(*formations):
    class _Cat:
        genesis_candidates = list(formations)

    return lambda world_id, *, state_dir=None: _Cat()


def _seed(tmp_path: Path, rows: list[dict]) -> None:
    world_model.bulk_upsert(WORLD, rows, state_dir=tmp_path)


def test_no_provider_is_typed_unavailable_not_hunt(tmp_path: Path):
    _seed(tmp_path, [{"sector_id": 1, "warps": [2], "landmarks": []}])
    plan = explore.plan_find_formations(
        WORLD, current_sector=1, turn_budget=5, epsilon=0.0, state_dir=tmp_path
    )
    assert plan.mode == "unavailable"
    assert plan.found is False
    assert plan.hunt is None
    assert plan.next_sector is None
    assert plan.targets == ()


def test_empty_catalog_hunts_via_map_fill(tmp_path: Path):
    _seed(
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 99], "landmarks": []},
        ],
    )
    plan = explore.plan_find_formations(
        WORLD,
        current_sector=1,
        turn_budget=5,
        epsilon=0.0,
        state_dir=tmp_path,
        catalog_provider=_fake_catalog(),
    )
    assert plan.found is False
    assert plan.mode in ("hunt", "exhausted")
    assert plan.mode != "unavailable"


def test_routes_toward_genesis_candidate(tmp_path: Path):
    _seed(
        tmp_path,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1, 3], "landmarks": []},
            {"sector_id": 3, "warps": [2], "landmarks": []},
        ],
    )
    plan = explore.plan_find_formations(
        WORLD,
        current_sector=1,
        turn_budget=5,
        epsilon=0.0,
        state_dir=tmp_path,
        catalog_provider=_fake_catalog(
            _FakeFormation("dead-end", (3,), entrance=3)
        ),
    )
    assert plan.found is True
    assert plan.mode == "route"
    assert plan.next_sector == 2
    assert plan.kind == "dead-end"


def test_arrived_when_already_at_entrance(tmp_path: Path):
    _seed(
        tmp_path,
        [
            {"sector_id": 3, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [3], "landmarks": []},
        ],
    )
    plan = explore.plan_find_formations(
        WORLD,
        current_sector=3,
        turn_budget=5,
        epsilon=0.0,
        state_dir=tmp_path,
        catalog_provider=_fake_catalog(
            _FakeFormation("dead-end", (3,), entrance=3)
        ),
    )
    assert plan.found is True
    assert plan.mode == "arrived"
    assert plan.next_sector is None


def test_catalog_mode_when_candidate_unreachable(tmp_path: Path):
    # Disjoint components: sitting in 1, candidate entrance 50 unknown/unlinked.
    _seed(tmp_path, [{"sector_id": 1, "warps": [2], "landmarks": []}])
    plan = explore.plan_find_formations(
        WORLD,
        current_sector=1,
        turn_budget=5,
        epsilon=0.0,
        state_dir=tmp_path,
        catalog_provider=_fake_catalog(
            _FakeFormation("bubble", (50, 51), entrance=50)
        ),
    )
    assert plan.found is True
    assert plan.mode == "catalog"
    assert plan.route is None
    assert plan.next_sector is None


def test_formations_modules_never_import_twclient():
    """Regression pin for the #142 landmine class."""
    roots = [
        Path(explore.__file__),
        Path(__file__),
    ]
    for path in roots:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("twclient"), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("twclient"), path
