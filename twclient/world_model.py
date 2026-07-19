"""World Model -- the persisted per-world sector database (TW-06).

Implements `knowledge/architecture/world-model.md`'s Schema and Write
Hooks sections: one JSON store per world (see `world_identity.py` for
the `world_id` keying rule this module treats as an opaque caller-
supplied string -- this module never computes one itself, so the two
concerns stay decoupled), holding one record per known sector:
`sector_id`, `warps`, `port`, `threats`, `landmarks`,
`formation_membership`, `last_seen_ts` -- exactly the canon shape.

Persistence layout: `state/world/<world_id>/sectors.json`, one file per
world -- this alone is the cross-world isolation guarantee (two worlds
never share a file, so they structurally cannot bleed into each other).

Concurrency: the flock + atomic-temp-then-rename + 0600 discipline is
copied from `player_bank.py` (the just-shipped, mack+cipher-hardened
reference) verbatim -- the daemon and CLI both write, so the
load-mutate-save race is real and the lock is mandatory, not optional.
The lock guards a sibling `<sectors.json>.lock` file per world (never
the store file itself), so lock-free readers (`get_sector`,
`all_sectors`, `query`) are never blocked by a held write lock --
readers are protected from a torn read by `save_store`'s atomic
rename, not by this lock.

**Field-level upsert semantics (the "additive, last-write-wins per
field" rule the canon's Write Hooks section describes):** `record`
passed to `upsert_sector`/`bulk_upsert` may be PARTIAL -- only
`sector_id` is required. Any other top-level field present in `record`
(`warps`, `port`, `threats`, `landmarks`, `formation_membership`)
*fully replaces* the corresponding stored field for that sector --
never sub-merged with the old value (e.g. an old and new `port`
commodities list are never unioned; the new one wins outright, per the
canon's "supersedes... rather than merging stale and fresh data").
Fields ABSENT from `record` are left untouched on the existing sector
entry -- this is the "additive" half: a warps-only write from movement
(no port info observed this pass) must not erase previously-learned
port data for that sector. `last_seen_ts` is always re-stamped on
every upsert, whether the caller supplies one or not.
"""

import contextlib
import copy
import datetime
import fcntl
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "state"
WORLD_DIR = STATE_DIR / "world"
SECTORS_FILENAME = "sectors.json"

STORE_VERSION = 1

_SECTOR_FIELDS = ("warps", "port", "threats", "landmarks", "formation_membership")


class WorldModelError(Exception):
    """Store-level errors: corrupt sectors.json, an unsupported
    version, a sector entry missing its (required) sector_id key, or a
    caller-supplied record missing sector_id."""


def _now_iso(clock=None):
    now = clock() if clock is not None else datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_sector(sector_id):
    return {
        "sector_id": sector_id,
        "warps": [],
        "port": None,
        "threats": {"mines": False, "fighters": None},
        "landmarks": [],
        "formation_membership": None,
        "last_seen_ts": None,
    }


def _new_store(world_id):
    return {"version": STORE_VERSION, "world_id": world_id, "sectors": {}}


def _store_path(world_id, state_dir=None):
    base = Path(state_dir) if state_dir is not None else WORLD_DIR
    return base / world_id / SECTORS_FILENAME


def _lock_path(path):
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def _store_lock(world_id, state_dir=None):
    """Exclusive `fcntl.flock`, held across a mutator's FULL
    load-mutate-save critical section -- mirrors `player_bank._bank_lock`
    exactly, one lock file per world (so two different worlds' writers
    never contend with each other)."""
    path = _store_path(world_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(path)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def load_store(world_id, state_dir=None):
    """Load the world's sector store, or return a fresh empty store if
    it doesn't exist yet -- that's the expected pre-first-visit state
    for a brand new world, never an error. A corrupt/truncated/empty
    file, an unsupported `version`, or a sector entry missing its
    (required) `sector_id` key are all treated as fatal structural
    corruption -- `WorldModelError`, naming the file, NEVER a silent
    reset to an empty store (that would be data loss dressed as
    recovery). Lock-free: safe for concurrent readers because
    `save_store`'s atomic rename means a read never observes a
    partially-written file, only a complete old or new one."""
    path = _store_path(world_id, state_dir)
    if not path.exists():
        return _new_store(world_id)
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise WorldModelError(
                f"world_model store is corrupt (invalid JSON): {path} ({e})"
            ) from e
    if not isinstance(data, dict):
        raise WorldModelError(
            f"world_model store has an invalid top-level shape (expected an object): {path}"
        )
    data.setdefault("version", STORE_VERSION)
    if data["version"] != STORE_VERSION:
        raise WorldModelError(
            f"unsupported world_model store version {data['version']!r} in {path} "
            f"(expected {STORE_VERSION})"
        )
    data.setdefault("world_id", world_id)
    data.setdefault("sectors", {})
    for key, entry in data["sectors"].items():
        if "sector_id" not in entry:
            raise WorldModelError(
                f"world_model sector entry {key!r} is missing sector_id in {path}"
            )
    return data


def save_store(store, world_id, state_dir=None):
    """Atomic write: temp-then-rename, chmod 0600 (mirrors
    `player_bank.save_bank`/`credentials._write_secrets` exactly), so a
    crash mid-write can never corrupt an existing store -- the
    destination only ever sees a complete, valid write. On ANY failure
    before the rename completes, the orphaned temp file is removed too."""
    path = _store_path(world_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, sort_keys=True)
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(str(tmp_path), str(path))
        os.chmod(path, 0o600)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def _merge_sector_locked(store, record, now):
    """Assumes the caller already holds `_store_lock` and owns `store`
    (a dict just returned by `load_store`, not yet saved) -- mutates it
    in place and returns the merged sector dict. Never acquires the
    lock itself: exists so `upsert_sector` and `bulk_upsert` can share
    this logic inside ONE lock acquisition each (mirrors
    `player_bank._add_player_locked`)."""
    if "sector_id" not in record:
        raise WorldModelError("upsert_sector: record is missing required 'sector_id' key")
    sector_id = record["sector_id"]
    key = str(sector_id)
    existing = store["sectors"].get(key)
    merged = dict(existing) if existing is not None else _default_sector(sector_id)
    for field in _SECTOR_FIELDS:
        if field in record:
            merged[field] = record[field]
    merged["sector_id"] = sector_id
    merged["last_seen_ts"] = record.get("last_seen_ts") or _now_iso(now)
    store["sectors"][key] = merged
    return merged


def upsert_sector(world_id, record, state_dir=None, now=None):
    """Write one (possibly partial) sector record into `world_id`'s
    store -- see module docstring for the field-level replace-not-merge
    semantics. Returns a deep copy of the resulting merged sector."""
    with _store_lock(world_id, state_dir=state_dir):
        store = load_store(world_id, state_dir=state_dir)
        merged = _merge_sector_locked(store, record, now)
        save_store(store, world_id, state_dir=state_dir)
    return copy.deepcopy(merged)


def bulk_upsert(world_id, records, state_dir=None, now=None):
    """Batch form of `upsert_sector` -- the write path a batch
    port/sector report (many sectors on one screen) or a density-scan
    exploration pass needs: every record in `records` is merged under
    ONE lock acquisition and ONE save, rather than one lock/save cycle
    per sector. Returns a list of deep copies of the merged sectors, in
    the same order as `records`."""
    if not records:
        return []
    with _store_lock(world_id, state_dir=state_dir):
        store = load_store(world_id, state_dir=state_dir)
        merged_list = [_merge_sector_locked(store, r, now) for r in records]
        save_store(store, world_id, state_dir=state_dir)
    return [copy.deepcopy(m) for m in merged_list]


def get_sector(world_id, sector_id, state_dir=None):
    """A single sector's record (deep copy -- mutating the return
    value never touches the live store), or `None` if this world has
    never seen that sector."""
    store = load_store(world_id, state_dir=state_dir)
    entry = store["sectors"].get(str(sector_id))
    return copy.deepcopy(entry) if entry is not None else None


def all_sectors(world_id, state_dir=None):
    """Every known sector in this world, sorted by `sector_id`, as deep
    copies (mutating the returned list/dicts never touches the live
    store)."""
    store = load_store(world_id, state_dir=state_dir)
    ordered = sorted(store["sectors"].items(), key=lambda kv: int(kv[0]))
    return [copy.deepcopy(entry) for _, entry in ordered]


def query(world_id, predicate, state_dir=None):
    """Sectors (deep copies) in this world for which `predicate(sector)`
    is truthy -- the read path higher-level consumers (routing,
    formation detection, trade-loop discovery, coaching) filter through
    rather than re-scanning `all_sectors` by hand each time."""
    return [s for s in all_sectors(world_id, state_dir=state_dir) if predicate(s)]


def write_from_state(world_id, parsed_state, state_dir=None, now=None):
    """Map a `state_parser.parse_state(...)` dict into a partial sector
    upsert -- the write-hook entry point every parsed game-state read
    calls. `parsed_state` has no dedicated sector-key of its own to
    anchor on beyond its own `sector` field, so a parse with no
    `sector` (nothing on screen anchoring a sector number) writes
    nothing and returns `None` -- there is no sector to attribute the
    rest of the reading to.

    Only `warps`/`port`/`threats` are mapped (the canon's Write Hooks
    section: "every parsed game-state read... writes its sector's
    port/threats fields") -- `landmarks`/`formation_membership` are
    populated by other passes (auto-explore, the formation detector),
    not by a raw state-parser read, so they're left untouched here
    (field-level upsert semantics: absent fields are preserved, not
    cleared). `state_parser.parse_state()` doesn't currently extract a
    port `class` or a `threats` shape at all -- this mapping is
    forward-compatible with whichever of those it grows next rather
    than inventing fields state_parser doesn't produce today."""
    sector_id = parsed_state.get("sector")
    if sector_id is None:
        return None

    record = {"sector_id": sector_id}
    if "warps" in parsed_state:
        record["warps"] = list(parsed_state["warps"])
    if "port" in parsed_state:
        parsed_port = parsed_state["port"] or {}
        record["port"] = {
            "class": parsed_port.get("class"),
            "commodities": [dict(c) for c in parsed_port.get("commodities", [])],
            "last_seen_ts": _now_iso(now),
        }
    if "threats" in parsed_state:
        record["threats"] = dict(parsed_state["threats"])

    return upsert_sector(world_id, record, state_dir=state_dir, now=now)
