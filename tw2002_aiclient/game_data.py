"""PWO-092 — Layer-B game-data store (schema + source gate + per-world persist).

Canon: ``canon/engine/game-data-store.md``. Portable semantics (Layer A) live
in canon only and carry **no** numbers. This module holds introspected
per-world rows (Layer B) and **rejects** any row whose ``source`` does not
begin with ``introspected`` — on both write and load.

Ceiling: fixture/offline introspector LIVE (PWO-092 Option A); no live TWGS
crawl/send in this module. No port-economics hypothesis floors (PWO-100).
Fact table only — never selects actions.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .world_model import WORLD_DIR

__all__ = [
    "CargoHoldRow",
    "GameData",
    "GameDataError",
    "ItemRow",
    "ScannerRow",
    "ShipRow",
    "TranswarpRow",
    "empty_game_data",
    "game_data_path",
    "load_game_data",
    "load_world_game_data",
    "persist_cargo_hold_row",
    "persist_ship_row",
    "save_world_game_data",
    "validate_cargo_hold_row",
    "validate_ship_row",
]

REQUIRED_SHIP_FIELDS = frozenset(
    {
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
    }
)
REQUIRED_CARGO_HOLD_FIELDS = frozenset({"cost_per_hold", "source", "last_verified_ts"})


class GameDataError(ValueError):
    """Schema or source-gate refusal for Layer-B game data."""


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
class CargoHoldRow:
    cost_per_hold: int
    source: str
    last_verified_ts: str


@dataclass(frozen=True)
class GameData:
    world_id: Optional[str] = None
    ships: tuple[ShipRow, ...] = field(default_factory=tuple)
    scanners: tuple[ScannerRow, ...] = field(default_factory=tuple)
    transwarp: tuple[TranswarpRow, ...] = field(default_factory=tuple)
    items: tuple[ItemRow, ...] = field(default_factory=tuple)
    cargo_holds: tuple[CargoHoldRow, ...] = field(default_factory=tuple)


def empty_game_data(world_id: Optional[str] = None) -> GameData:
    return GameData(world_id=world_id)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_introspected(source: Any, *, kind: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise GameDataError(f"{kind}.source must be a non-empty string")
    if not source.startswith("introspected"):
        raise GameDataError(
            f"{kind}.source must start with 'introspected' "
            f"(got {source!r} — static-authored numbers are forbidden)"
        )
    return source


def _require_ts(value: Any, *, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GameDataError(f"{kind}.last_verified_ts must be a non-empty ISO-8601 string")
    return value


def validate_ship_row(row: Mapping[str, Any]) -> ShipRow:
    missing = REQUIRED_SHIP_FIELDS - frozenset(row.keys())
    if missing:
        raise GameDataError(f"ship row missing fields: {sorted(missing)}")
    abilities = row["special_abilities"]
    if abilities is None:
        abilities = ()
    if not isinstance(abilities, (list, tuple)):
        raise GameDataError("ship.special_abilities must be a list")
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



def validate_cargo_hold_row(row: Mapping[str, Any]) -> CargoHoldRow:
    """Validate a cargo-hold price row (source gate + required fields)."""
    missing = REQUIRED_CARGO_HOLD_FIELDS - frozenset(row.keys())
    if missing:
        raise GameDataError(f"cargo_hold row missing fields: {sorted(missing)}")
    return CargoHoldRow(
        cost_per_hold=int(row["cost_per_hold"]),
        source=_require_introspected(row["source"], kind="cargo_hold"),
        last_verified_ts=_require_ts(row["last_verified_ts"], kind="cargo_hold"),
    )

def _ship_to_dict(ship: ShipRow) -> dict:
    out = asdict(ship)
    out["special_abilities"] = list(ship.special_abilities)
    return out


def load_game_data(path: str | Path) -> GameData:
    """Load + re-validate a game-data JSON document (source gate on every row)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GameDataError("game_data root must be a JSON object")
    # Drop fixture-only commentary keys.
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
    cargo_holds = tuple(
        CargoHoldRow(
            cost_per_hold=int(c["cost_per_hold"]),
            source=_require_introspected(c["source"], kind="cargo_hold"),
            last_verified_ts=_require_ts(c["last_verified_ts"], kind="cargo_hold"),
        )
        for c in raw.get("cargo_holds") or ()
    )
    world_id = raw.get("world_id")
    return GameData(
        world_id=None if world_id is None else str(world_id),
        ships=ships,
        scanners=scanners,
        transwarp=transwarp,
        items=items,
        cargo_holds=cargo_holds,
    )


def game_data_to_dict(data: GameData) -> dict:
    return {
        "world_id": data.world_id,
        "ships": [_ship_to_dict(s) for s in data.ships],
        "scanners": [asdict(s) for s in data.scanners],
        "transwarp": [asdict(t) for t in data.transwarp],
        "items": [asdict(i) for i in data.items],
        "cargo_holds": [asdict(c) for c in data.cargo_holds],
    }


def game_data_path(world_id: str, *, state_dir: str | Path | None = None) -> Path:
    if not isinstance(world_id, str) or not world_id.strip():
        raise GameDataError("world_id must be a non-empty string")
    if "/" in world_id or "\\" in world_id or world_id in {".", ".."}:
        raise GameDataError(f"world_id is not a safe path segment: {world_id!r}")
    base = Path(state_dir) if state_dir is not None else WORLD_DIR
    return base / world_id / "game_data.json"


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def _file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _lock_path(path)
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def load_world_game_data(world_id: str, *, state_dir: str | Path | None = None) -> GameData:
    path = game_data_path(world_id, state_dir=state_dir)
    if not path.exists():
        return empty_game_data(world_id=world_id)
    data = load_game_data(path)
    # On-disk world_id must match the path key when present.
    if data.world_id is not None and data.world_id != world_id:
        raise GameDataError(
            f"game_data world_id {data.world_id!r} does not match path key {world_id!r}"
        )
    if data.world_id is None:
        return GameData(
            world_id=world_id,
            ships=data.ships,
            scanners=data.scanners,
            transwarp=data.transwarp,
            items=data.items,
            cargo_holds=data.cargo_holds,
        )
    return data


def save_world_game_data(data: GameData, *, state_dir: str | Path | None = None) -> Path:
    """Persist a fully validated GameData document for ``data.world_id``."""
    if not data.world_id:
        raise GameDataError("cannot persist game_data without world_id")
    # Re-validate every row through the source gate before touching disk.
    revalidated = load_game_data_from_mapping(game_data_to_dict(data))
    path = game_data_path(revalidated.world_id, state_dir=state_dir)
    with _file_lock(path):
        _atomic_write_json(path, game_data_to_dict(revalidated))
    return path


def load_game_data_from_mapping(raw: Mapping[str, Any]) -> GameData:
    """Validate an in-memory mapping with the same gates as ``load_game_data``."""
    if not isinstance(raw, Mapping):
        raise GameDataError("game_data root must be a mapping")
    # Reuse file loader via a temp round-trip would be slow — inline.
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
    cargo_holds = tuple(
        CargoHoldRow(
            cost_per_hold=int(c["cost_per_hold"]),
            source=_require_introspected(c["source"], kind="cargo_hold"),
            last_verified_ts=_require_ts(c["last_verified_ts"], kind="cargo_hold"),
        )
        for c in raw.get("cargo_holds") or ()
    )
    world_id = raw.get("world_id")
    return GameData(
        world_id=None if world_id is None else str(world_id),
        ships=ships,
        scanners=scanners,
        transwarp=transwarp,
        items=items,
        cargo_holds=cargo_holds,
    )


def persist_ship_row(
    world_id: str, row: Mapping[str, Any], *, state_dir: str | Path | None = None
) -> ShipRow:
    """Validate + upsert one ship row into the world's game_data.json."""
    payload = dict(row)
    if not payload.get("last_verified_ts"):
        payload["last_verified_ts"] = _now_iso()
    ship = validate_ship_row(payload)
    with _file_lock(game_data_path(world_id, state_dir=state_dir)):
        data = load_world_game_data(world_id, state_dir=state_dir)
        ships = [s for s in data.ships if s.ship_name != ship.ship_name]
        ships.append(ship)
        updated = GameData(
            world_id=world_id,
            ships=tuple(ships),
            scanners=data.scanners,
            transwarp=data.transwarp,
            items=data.items,
            cargo_holds=data.cargo_holds,
        )
        path = game_data_path(world_id, state_dir=state_dir)
        _atomic_write_json(path, game_data_to_dict(updated))
    return ship


def persist_cargo_hold_row(
    world_id: str, row: Mapping[str, Any], *, state_dir: str | Path | None = None
) -> CargoHoldRow:
    """Validate + replace the world's singleton cargo-hold quote row.

    StarDock quotes one per-hold price at a time; the store keeps the latest
    introspected quote (not a multi-row history).
    """
    payload = dict(row)
    if not payload.get("last_verified_ts"):
        payload["last_verified_ts"] = _now_iso()
    hold = validate_cargo_hold_row(payload)
    with _file_lock(game_data_path(world_id, state_dir=state_dir)):
        data = load_world_game_data(world_id, state_dir=state_dir)
        updated = GameData(
            world_id=world_id,
            ships=data.ships,
            scanners=data.scanners,
            transwarp=data.transwarp,
            items=data.items,
            cargo_holds=(hold,),
        )
        path = game_data_path(world_id, state_dir=state_dir)
        _atomic_write_json(path, game_data_to_dict(updated))
    return hold
