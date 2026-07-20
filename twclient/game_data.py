"""TW-24 Layer B — per-server game-data schema + loader (client-side).

Portable semantics live in knowledge/reference/tw2002-ships-and-equipment.md
(OKF Layer A). Numeric rows are filled by TW-27 introspection into a
per-world store — NEVER invent stock TW2002 numbers here. This module
defines the schema, validation (source must be introspected), a
persist/query path into that per-world store, and a bridge to ShipSpec
for TW-30.

**Persist path (TW-26/27 write lane):** `persist_ship_row`/`get_ship`/
`list_ships`/`list_flyable_ships` below are a thin, schema-validated
bridge over `game_knowledge.py`'s already-hardened per-world "ships"
game-data table (flock + atomic-write + 0600, one file per world at
`state/world/<world_id>/game_knowledge.json`) — this module does NOT
open a second/parallel store. `validate_ship_row` (the introspected-
only + required-fields gate `load_game_data` already runs at load time)
gates the WRITER too: a non-introspected or malformed row is rejected
at `persist_ship_row()`, before the store is ever touched, not just
later on read."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from twclient.ship_upgrade_decision import ShipSpec

from . import game_knowledge

# The game_knowledge.py game-data table this module's ships persist
# into -- must match one of game_knowledge.GAME_DATA_TABLES exactly (a
# typo'd table name fails loudly there, not silently here).
SHIPS_TABLE = "ships"

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


# -- persist/query path (TW-26/27 write lane) --------------------------------
#
# Bridges validated ShipRows into game_knowledge.py's already-hardened
# per-world "ships" game-data table -- see this module's docstring.
# `state_dir` (default None -> the real `state/` tree) is threaded
# through every function below purely so tests can point it at
# `tmp_path`; production callers never need to pass it.


def _ship_row_fields(ship: ShipRow) -> dict:
    """The full REQUIRED_SHIP_FIELDS shape for `ship`, as a plain dict --
    used both as the `fields=` payload `upsert_game_data_row` persists
    and (read back with `key`/`source`/`last_verified_ts` re-stamped by
    the store) as exactly what `validate_ship_row` needs to reconstruct
    a `ShipRow` on the read side, so persist and query round-trip
    through the identical shape."""
    return {
        "ship_name": ship.ship_name,
        "max_holds": ship.max_holds,
        "max_fighters": ship.max_fighters,
        "max_shields": ship.max_shields,
        "combat_odds_modifier": ship.combat_odds_modifier,
        "turns_per_warp": ship.turns_per_warp,
        "base_cost_credits": ship.base_cost_credits,
        "alignment_requirement": ship.alignment_requirement,
        "rank_requirement": ship.rank_requirement,
        "transwarp_capable": ship.transwarp_capable,
        "special_abilities": list(ship.special_abilities),
        "source": ship.source,
        "last_verified_ts": ship.last_verified_ts,
    }


def persist_ship_row(
    world_id: str, row: Mapping[str, Any], *, state_dir: str | Path | None = None
) -> ShipRow:
    """Validate + persist one introspected ship row into `world_id`'s
    per-world game-data store. `validate_ship_row` -- the SAME gate
    `load_game_data` runs at load time -- runs here (after the
    write-time timestamp stamp below): a non-introspected `source` or
    any missing/malformed required field OTHER than `last_verified_ts`
    raises `ValueError` before the store is ever touched (nothing is
    written, no lock is taken), never silently persisted and only
    caught later on read.

    **This is the introspector's documented write-time clock (seam fix,
    2026-07-19 integration review).** A pure parser (TW-27's
    introspector) has no clock and deliberately OMITS `last_verified_ts`
    from every row it emits -- its own docstring names *this* function
    as the caller responsible for stamping it at write time. A row
    arriving here with no (or an empty/falsy) `last_verified_ts` is
    stamped fresh, via the SAME clock convention
    `game_knowledge.upsert_game_data_row` itself re-stamps with, BEFORE
    `validate_ship_row` runs -- so a ts-less introspected row is
    accepted, not rejected as "missing fields". A caller that DOES
    supply its own `last_verified_ts` is left alone here; either way
    the store's own upsert re-stamps it fresh again on persist (see
    that module's docstring), so the two stamps never disagree and a
    caller-supplied value is never trusted verbatim past this point --
    only its PRESENCE (not its exact value) matters to this stamp.

    Persisting the same `ship.ship_name` again (e.g. a newer
    introspection capture superseding an older one) overwrites the
    prior row wholesale -- `game_knowledge.upsert_game_data_row`'s
    existing last-write-wins-per-key discipline (the same "supersedes,
    never sub-merges stale and fresh data" rule `world_model.py` uses)
    ; there is no partial/field-level merge for a ship row the way
    `world_model.py` does for a sector, because one introspection
    capture (e.g. one shipyard listing) is always a whole, self-
    consistent snapshot, never a partial one.

    Returns the persisted row re-validated as a `ShipRow`, round-tripped
    through the store -- so the caller sees exactly what a subsequent
    `get_ship`/`list_ships` call would see, not just an echo of its own
    input."""
    if not row.get("last_verified_ts"):
        row = dict(row)
        row["last_verified_ts"] = game_knowledge._now_iso()
    ship = validate_ship_row(row)
    path = game_knowledge.knowledge_path_for_world(world_id, state_dir=state_dir)
    stored = game_knowledge.upsert_game_data_row(
        path, SHIPS_TABLE, ship.ship_name, _ship_row_fields(ship), source=ship.source
    )
    return validate_ship_row(stored)


def get_ship(world_id: str, ship_name: str, *, state_dir: str | Path | None = None) -> Optional[ShipRow]:
    """A single ship by name in `world_id`'s store, re-validated as a
    `ShipRow`, or `None` if this world has never had that ship
    persisted. Two different worlds never share rows -- see
    `game_knowledge.py`'s per-world keying -- so a name persisted only
    in one world is invisible from another."""
    path = game_knowledge.knowledge_path_for_world(world_id, state_dir=state_dir)
    row = game_knowledge.get_game_data_row(path, SHIPS_TABLE, ship_name)
    return validate_ship_row(row) if row is not None else None


def list_ships(world_id: str, *, state_dir: str | Path | None = None) -> tuple[ShipRow, ...]:
    """Every ship persisted in `world_id`'s store, re-validated as
    `ShipRow`s, in insertion order."""
    path = game_knowledge.knowledge_path_for_world(world_id, state_dir=state_dir)
    rows = game_knowledge.list_game_data_rows(path, SHIPS_TABLE)
    return tuple(validate_ship_row(r) for r in rows)


def list_flyable_ships(
    world_id: str,
    *,
    alignment: Optional[int] = None,
    state_dir: str | Path | None = None,
) -> tuple[ShipRow, ...]:
    """Ships in `world_id`'s store whose alignment gate the player's
    current `alignment` satisfies -- an ungated ship
    (`alignment_requirement is None`) always passes; a numeric
    requirement passes only when `alignment` is given AND `>=` it, per
    tw2002-ships-and-equipment.md's "Minimum alignment to acquire, if
    gated" schema semantics.

    `alignment=None` (caller doesn't know/hasn't supplied the player's
    current standing) is treated conservatively: only ungated ships
    pass -- mirroring `ship_upgrade_decision.py`'s refuse-when-
    uncommissioned posture rather than assuming an unknown alignment
    clears every gate.

    Deliberately does NOT also filter on `rank_requirement` -- no rank
    ORDERING exists anywhere in this codebase yet (it's a free-form
    string per the schema doc, not a comparable value), so inventing
    one here would be new, unreviewed canon rather than a mechanical
    filter. Callers needing rank-aware filtering see the raw
    `rank_requirement` on each returned `ShipRow` and can apply their
    own comparison once that canon exists."""

    def _flyable(ship: ShipRow) -> bool:
        if ship.alignment_requirement is None:
            return True
        return alignment is not None and alignment >= ship.alignment_requirement

    return tuple(s for s in list_ships(world_id, state_dir=state_dir) if _flyable(s))
