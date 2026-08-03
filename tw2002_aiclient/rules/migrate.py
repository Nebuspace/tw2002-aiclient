"""Operator-data layout migrate for the reflex rule library (PWO-090 residual).

Not rule *authoring* — that stays exclusively in :mod:`tw2002_aiclient.rules.writer`.
This module only copies legacy flat ``state/rules`` into
``state/world/<world_id>/rules`` once (DECISION-RULES-WORLD-MIGRATE-ON-READ).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .store import RULES_DIRNAME, STATE_DIR, rules_dir

__all__ = [
    "legacy_flat_rules_dir",
    "migrate_flat_rules_to_world",
]


def legacy_flat_rules_dir(state_dir=None) -> Path:
    """Explicit legacy flat ``state/rules`` (never world-scoped)."""
    base = Path(state_dir) if state_dir is not None else STATE_DIR
    return base / RULES_DIRNAME


def migrate_flat_rules_to_world(world_id: str, *, state_dir=None) -> dict:
    """Copy legacy flat rules into ``state/world/<world_id>/rules`` once.

    Policy (DECISION-RULES-WORLD-MIGRATE-ON-READ, hub GO 2026-08-03):

    * Fresh installs / empty flat → no-op.
    * World store already has ``*.json`` → no-op.
    * Flat has ``*.json`` and world store empty → copy (incl. ``_drafts/``).
    * Never deletes the flat tree.

    Returns ``{"migrated": bool, "copied": int, "world_dir": str, "flat_dir": str}``.
    """
    if world_id is None or not str(world_id).strip():
        raise ValueError("world_id is required for migrate_flat_rules_to_world")
    wid = str(world_id).strip()
    flat = legacy_flat_rules_dir(state_dir)
    world = rules_dir(state_dir, world_id=wid)
    result = {
        "migrated": False,
        "copied": 0,
        "world_dir": str(world),
        "flat_dir": str(flat),
    }

    def _json_files(root: Path) -> list[Path]:
        # Open-and-classify — never Path.exists/is_file/is_dir.
        try:
            candidates = sorted(root.rglob("*.json"))
        except OSError:
            return []
        out: list[Path] = []
        for path in candidates:
            try:
                with path.open("rb"):
                    pass
            except OSError:
                continue
            out.append(path)
        return out

    if _json_files(world):
        return result
    flat_files = _json_files(flat)
    if not flat_files:
        return result

    world.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in flat_files:
        rel = src.relative_to(flat)
        dest = world / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("xb") as out_f, src.open("rb") as in_f:
                shutil.copyfileobj(in_f, out_f)
        except FileExistsError:
            continue
        except OSError:
            continue
        copied += 1
    result["migrated"] = copied > 0
    result["copied"] = copied
    return result
