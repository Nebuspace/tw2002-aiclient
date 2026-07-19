"""TW-24 Layer B — per-server game-data schema + loader (client-side).

Portable semantics live in knowledge/reference/tw2002-ships-and-equipment.md
(OKF Layer A). Numeric rows are filled by TW-27 introspection into a
per-world store — NEVER invent stock TW2002 numbers here. This module only
defines the schema, validation (source must be introspected), and a bridge
to ShipSpec for TW-30.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from twclient.ship_upgrade_decision import ShipSpec

REQUIRED_SHIP_FIELDS = frozenset({
    "ship_name",
    "max_holds",
    "max_fighters",
    "max_shields",
    "combat_odds_modifier",
    "turns_per_warp",
    "base_cost_credits",
    "alignment_requirement",
    "rank_requirement",
    "transwarp_capable",
    "special_abilities",
    "source",
    "last_verified_ts",
})


@dataclass(frozen=True)
class ShipRow:
    ship_name: str
    max_holds: int
    max_fighters: int
    max_shields: int
    combat_odds_modifier: float
    turns_per_warp: int
    base_cost_credits: int
    alignment_requirement: Optional[int]
    rank_requirement: Optional[str]
    transwarp_capable: bool
    special_abilities: tuple[str, ...]
    source: str
    last_verified_ts: str


@dataclass(frozen=True)
class ScannerRow:
    scanner_type: str
    cost_credits: int
    capability_notes: str
    source: str
    last_verified_ts: str


@dataclass(frozen=True)
class TranswarpRow:
    cost_credits: int
    range_notes: str
    source: str
    last_verified_ts: str


@dataclass(frozen=True)
class ItemRow:
    item_name: str
    cost_credits: int
    effect_notes: str
    source: str
    last_verified_ts: str


@dataclass(frozen=True)
class GameData:
    world_id: Optional[str] = None
    ships: tuple[ShipRow, ...] = field(default_factory=tuple)
    scanners: tuple[ScannerRow, ...] = field(default_factory=tuple)
    transwarp: tuple[TranswarpRow, ...] = field(default_factory=tuple)
    items: tuple[ItemRow, ...] = field(default_factory=tuple)


def _require_introspected(source: Any, *, kind: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"{kind}.source must be a non-empty string")
    if not source.startswith("introspected"):
        raise ValueError(
            f"{kind}.source must start with 'introspected' "
            f"(got {source!r} — static-authored numbers are forbidden)"
        )
    return source


def _require_ts(value: Any, *, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{kind}.last_verified_ts must be a non-empty ISO-8601 string")
    return value


def validate_ship_row(row: Mapping[str, Any]) -> ShipRow:
    missing = REQUIRED_SHIP_FIELDS - frozenset(row.keys())
    if missing:
        raise ValueError(f"ship row missing fields: {sorted(missing)}")
    abilities = row["special_abilities"]
    if abilities is None:
        abilities = ()
    if not isinstance(abilities, (list, tuple)):
        raise ValueError("ship.special_abilities must be a list")
    align = row["alignment_requirement"]
    rank = row["rank_requirement"]
    return ShipRow(
        ship_name=str(row["ship_name"]),
        max_holds=int(row["max_holds"]),
        max_fighters=int(row["max_fighters"]),
        max_shields=int(row["max_shields"]),
        combat_odds_modifier=float(row["combat_odds_modifier"]),
        turns_per_warp=int(row["turns_per_warp"]),
        base_cost_credits=int(row["base_cost_credits"]),
        alignment_requirement=None if align is None else int(align),
        rank_requirement=None if rank is None else str(rank),
        transwarp_capable=bool(row["transwarp_capable"]),
        special_abilities=tuple(str(a) for a in abilities),
        source=_require_introspected(row["source"], kind="ship"),
        last_verified_ts=_require_ts(row["last_verified_ts"], kind="ship"),
    )


def empty_game_data(world_id: Optional[str] = None) -> GameData:
    return GameData(world_id=world_id)


def load_game_data(path: str | Path) -> GameData:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("game_data root must be a JSON object")
    ships = tuple(validate_ship_row(s) for s in raw.get("ships") or ())
    scanners = tuple(
        ScannerRow(
            scanner_type=str(s["scanner_type"]),
            cost_credits=int(s["cost_credits"]),
            capability_notes=str(s.get("capability_notes") or ""),
            source=_require_introspected(s["source"], kind="scanner"),
            last_verified_ts=_require_ts(s["last_verified_ts"], kind="scanner"),
        )
        for s in raw.get("scanners") or ()
    )
    transwarp = tuple(
        TranswarpRow(
            cost_credits=int(t["cost_credits"]),
            range_notes=str(t.get("range_notes") or ""),
            source=_require_introspected(t["source"], kind="transwarp"),
            last_verified_ts=_require_ts(t["last_verified_ts"], kind="transwarp"),
        )
        for t in raw.get("transwarp") or ()
    )
    items = tuple(
        ItemRow(
            item_name=str(i["item_name"]),
            cost_credits=int(i["cost_credits"]),
            effect_notes=str(i.get("effect_notes") or ""),
            source=_require_introspected(i["source"], kind="item"),
            last_verified_ts=_require_ts(i["last_verified_ts"], kind="item"),
        )
        for i in raw.get("items") or ()
    )
    world_id = raw.get("world_id")
    return GameData(
        world_id=None if world_id is None else str(world_id),
        ships=ships,
        scanners=scanners,
        transwarp=transwarp,
        items=items,
    )


def ship_row_to_spec(ship: ShipRow, *, commissioned: bool = True) -> ShipSpec:
    return ShipSpec(
        name=ship.ship_name,
        cost=ship.base_cost_credits,
        holds=ship.max_holds,
        turns_per_warp=ship.turns_per_warp,
        fighters=ship.max_fighters,
        shields=ship.max_shields,
        alignment_req=ship.alignment_requirement or 0,
        commissioned=commissioned,
    )
