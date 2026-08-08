"""World Model -- the persisted per-world sector database (TW-06).

Implements `knowledge/architecture/world-model.md`'s Schema and Write
Hooks sections: one JSON store per world (see `world_identity.py` for
the `world_id` keying rule this module treats as an opaque caller-
supplied string -- this module never computes one itself, so the two
concerns stay decoupled), holding one record per known sector:
`sector_id`, `warps`, `port`, `threats`, `landmarks`,
`formation_membership`, `last_seen_ts` -- exactly the canon shape.

**Persistence layout (mack Finding 3, 2026-07-19 hardening pass):** ONE
FILE PER SECTOR -- `state/world/<world_id>/sectors/<sector_id>.json` --
not one big `sectors.json` per world. The original single-file-per-
world design made every write O(total known sectors) (a full
load+full-rewrite on every upsert, ~38ms @ 2000 sectors measured live)
and forced every writer through ONE lock regardless of which sector it
touched (two threads writing DIFFERENT sectors serialized behind each
other for no reason -- the daemon is `ThreadingMixIn`, so this was
reachable in real play). Per-sector files make a single-sector write
O(1) (only that file is read/rewritten) and give the flock per-sector
scope (`<sector_id>.json.lock`, not a world-wide lock) -- concurrent
writers touching DIFFERENT sectors in the same world no longer contend
at all. Cross-world isolation is still the structural guarantee it
always was: two worlds never share a directory, so they structurally
cannot bleed into each other. This was a greenfield change (no
`state/world/` data existed anywhere yet) -- no migration was needed.

Concurrency: the flock + atomic-temp-then-rename + 0600 discipline is
copied from `player_bank.py` (the just-shipped, mack+cipher-hardened
reference) verbatim -- the daemon and CLI both write, so the
load-mutate-save race is real and the lock is mandatory, not optional.
The lock guards a sibling `<sector_id>.json.lock` file per sector
(never the sector file itself), so lock-free readers (`get_sector`,
`all_sectors`, `query`) are never blocked by a held write lock --
readers are protected from a torn read by the atomic rename, not by
this lock.

**`last_seen_ts` always advances on a genuine observation (Samantha's
2026-07-19 follow-up ruling, superseding the original mack Finding 3a
dedup no-op):** an earlier hardening pass here made `upsert_sector`
skip the lock and the disk write ENTIRELY when the merge was a true
content no-op, to cut write volume in a `tw play` loop. That silently
froze `last_seen_ts` on a genuine, unchanged re-observation -- wrong,
since `last_seen_ts` is the canon's "I was actually here, this
recently" staleness marker a future freshness/rescan policy needs to
stay honest, not a "content last changed" marker. Per-sector
persistence (the "Persistence layout" section above) already made a
single write O(1) and cheap (~1ms measured) -- comparable to the
no-op's own bookkeeping cost -- so the removed skip's benefit was
marginal next to the correctness cost. `upsert_sector` now always
acquires the lock and always writes, so `last_seen_ts` always
re-stamps on every call, exactly as the "Field-level upsert semantics"
section below has always documented.

**Field-level upsert semantics (the "additive, last-write-wins per
field" rule the canon's Write Hooks section describes):** `record`
passed to `upsert_sector`/`bulk_upsert` may be PARTIAL -- only
`sector_id` is required. Any other top-level field present in `record`
(`warps`, `port`, `threats`, `formation_membership` -- but see
`landmarks` below) *fully replaces* the corresponding stored field --
never sub-merged with the old value (e.g. an old and new `port`
commodities list are never unioned; the new one wins outright, per the
canon's "supersedes... rather than merging stale and fresh data").
Fields ABSENT from `record` are left untouched on the existing sector
entry -- this is the "additive" half: a warps-only write from movement
(no port info observed this pass) must not erase previously-learned
port data for that sector. `last_seen_ts` is always re-stamped on
every upsert, whether the caller supplies one or not.

**`landmarks` is the one UNIONING field** (`_merge_landmarks`, which
carries the full argument). Replace semantics cannot hold for it: canon
requires that a plain visit never clear a landmark, and no readable
screen ever says "there is positively no landmark here" -- so an
observation that merely failed to notice would erase one that did.
Union makes that structural: no argument to an upsert can shrink the
stored set. Removal, if it is ever needed, owes its own deliberate path.

**Nested port field-level merge (mack Finding 1, 2026-07-19
hardening pass):** the `port` field is the ONE exception to "fully
replaces, never sub-merged" above -- when `record["port"]` is present
as a dict (not an explicit `None`), its OWN sub-fields (`class`,
`commodities`, `last_seen_ts`) get the SAME additive treatment the top
level already gets, one level deeper. Why: `state_parser.parse_state()`
extracts port `commodities` from an ordinary port-trade screen but
NEVER extracts a `class` at all -- `write_from_state()`'s old mapping
built `{"class": parsed_port.get("class"), ...}`, which is `None` for
every ordinary visit, and because `port` was replaced WHOLESALE, that
explicit `None` CLOBBERED a `class` a previous CIM `bulk_upsert` had
already learned. The fix is symmetric with the top-level rule: a
sub-key ABSENT from the incoming `port` dict is preserved from
whatever's already stored; a sub-key PRESENT (even if its value is
itself `None`) replaces. Only `class` gets a synthetic default (`None`)
when there's NEITHER an incoming value NOR anything already stored --
`commodities`/`last_seen_ts` are never invented out of thin air that
way, since every real caller always supplies both (only `class` has the
documented never-observed-by-a-plain-screen-visit gap). `write_from_state()`
now OMITS the `class` key entirely rather than writing an explicit
`None` for a class it never observed -- see its own docstring. An
explicit top-level `record["port"] = None` (as opposed to a dict) is
NOT run through this nested merge -- that is still an unambiguous,
deliberate "this sector has no port, clear whatever was there"
wholesale reset, exactly like any other top-level field's
explicit-value-provided case.
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
SECTORS_SUBDIR = "sectors"

_SECTOR_FIELDS = (
    "warps",
    "port",
    "threats",
    "landmarks",
    "formation_membership",
    "density_scan",
)
_PORT_FIELDS = ("class", "commodities", "last_seen_ts")

#: Verification stamp for density-scan writeback until a live multi-sector
#: capture confirms the row grammar (canon/engine/world-model.md).
DENSITY_SCAN_VERIFICATION = "HYPOTHESIS"


class WorldModelError(Exception):
    """Store-level errors: a corrupt `<sector_id>.json`, a sector file
    with an invalid (non-object) shape, a sector file missing its
    (required) `sector_id` key, or a caller-supplied record missing
    `sector_id`."""


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


def _default_port():
    """Only `class` is defaulted on a brand-new port with no incoming
    value for it -- `commodities`/`last_seen_ts` are NOT invented out of
    thin air when a fresh write doesn't supply them (every real caller
    -- `write_from_state`, the CIM batch mapping -- always supplies
    both, so there's no real-world path where they'd need a synthetic
    default; only `class` has the documented "a real screen visit never
    observes this at all" gap `_merge_port`'s docstring explains)."""
    return {"class": None}


def _world_dir(world_id, state_dir=None):
    base = Path(state_dir) if state_dir is not None else WORLD_DIR
    return base / world_id


def _sectors_dir(world_id, state_dir=None):
    return _world_dir(world_id, state_dir=state_dir) / SECTORS_SUBDIR


def _sector_path(world_id, sector_id, state_dir=None):
    return _sectors_dir(world_id, state_dir=state_dir) / f"{sector_id}.json"


def _lock_path(path):
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def _sector_lock(world_id, sector_id, state_dir=None):
    """Exclusive `fcntl.flock`, held across a mutator's FULL
    load-mutate-save critical section for ONE sector -- mirrors
    `player_bank._bank_lock`'s discipline, scoped per-sector so two
    writers touching DIFFERENT sectors in the same world never contend
    (mack Finding 3, hot-path + lock-contention hardening)."""
    path = _sector_path(world_id, sector_id, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(path)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _load_sector_file(world_id, sector_id, state_dir=None):
    """One sector's on-disk record, or `None` if this world has never
    written that sector yet -- the expected pre-first-visit state,
    never an error. A corrupt/truncated/empty file, a non-object
    shape, or a missing (required) `sector_id` key are all fatal
    structural corruption -- `WorldModelError`, naming the file, NEVER
    a silent reset to an empty/default sector (that would be data loss
    dressed as recovery). Lock-free: safe for concurrent readers
    because `_save_sector_file`'s atomic rename means a read never
    observes a partially-written file, only a complete old or new
    one."""
    path = _sector_path(world_id, sector_id, state_dir=state_dir)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise WorldModelError(
                f"world_model sector file is corrupt (invalid JSON): {path} ({e})"
            ) from e
    if not isinstance(data, dict):
        raise WorldModelError(
            f"world_model sector file has an invalid shape (expected an object): {path}"
        )
    if "sector_id" not in data:
        raise WorldModelError(f"world_model sector file is missing sector_id: {path}")
    return data


def _save_sector_file(world_id, sector_id, record, state_dir=None):
    """Atomic write: temp-then-rename, chmod 0600 (mirrors
    `player_bank.save_bank`/`credentials._write_secrets` exactly), so a
    crash mid-write can never corrupt an existing sector file -- the
    destination only ever sees a complete, valid write. On ANY failure
    before the rename completes, the orphaned temp file is removed
    too."""
    path = _sector_path(world_id, sector_id, state_dir=state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, sort_keys=True)
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(str(tmp_path), str(path))
        os.chmod(path, 0o600)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def _merge_port(existing_port, incoming_port):
    """Nested field-level merge for the `port` sub-dict -- see the
    module docstring's "Nested port field-level merge" section (mack
    Finding 1). `incoming_port` is only ever partial the same way a
    top-level `record` is: a sub-key present (even if its value is
    itself `None`) replaces; a sub-key ABSENT is preserved from
    whatever's already stored (or the default if nothing's stored
    yet)."""
    merged_port = dict(existing_port) if existing_port is not None else _default_port()
    for subfield in _PORT_FIELDS:
        if subfield in incoming_port:
            merged_port[subfield] = incoming_port[subfield]
    return merged_port


def _merge_landmarks(existing, incoming):
    """Union, never replace — landmarks ACCUMULATE.

    The one field whose upsert is additive rather than last-write-wins, and
    the exception is deliberate. Canon (`world-model.md`) requires that a
    plain visit never clears a landmark, and the reason is that no screen
    the trainer can read says *"there is positively no landmark here"* — a
    sector display that does not mention StarDock is silence, not a denial.
    Under the module's ordinary replace semantics, one observation that
    happened not to notice would erase one that did, and the erasure is
    indistinguishable from never having found it.

    Union makes that structural rather than remembered: there is no argument
    to this function that shrinks the stored set, so no future caller can
    reintroduce the clearing bug by passing `[]`. (A landmark that becomes
    genuinely wrong is a *correction*, which needs a deliberate removal path
    and an observation that can justify it — neither exists yet, and
    inventing one here would be the same guess in the other direction.)

    Dedup is **casefold**-based to match `explore.find_landmark_sectors`,
    which casefolds both sides: without it `stardock` and `StarDock` are one
    landmark to the reader and two to the store. Existing order is kept and
    new tokens append, so the record stays stable and diffable across runs.
    Non-string entries are dropped rather than stored — a landmarks list is a
    list of names, and anything else would only ever fail to match a lookup.
    """
    out: list = []
    seen: set = set()
    for source in (existing or (), incoming or ()):
        if isinstance(source, (str, bytes)):
            # A bare string is iterable, and iterating it would store one
            # landmark per CHARACTER. Refuse rather than silently shred it.
            continue
        try:
            items = list(source)
        except TypeError:
            continue
        for item in items:
            if not isinstance(item, str) or not item:
                continue
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def _compute_merged_sector(existing, record, now):
    """Pure computation, no I/O and no lock -- given the record already
    stored for this sector (or `None`) and an incoming partial
    `record`, returns what the merged sector WOULD be, without
    persisting anything."""
    if "sector_id" not in record:
        raise WorldModelError("upsert_sector: record is missing required 'sector_id' key")
    sector_id = record["sector_id"]
    merged = dict(existing) if existing is not None else _default_sector(sector_id)
    for field in _SECTOR_FIELDS:
        if field not in record:
            continue
        if field == "port" and record["port"] is not None:
            merged["port"] = _merge_port(merged.get("port"), record["port"])
        elif field == "landmarks":
            merged["landmarks"] = _merge_landmarks(merged.get("landmarks"), record["landmarks"])
        else:
            merged[field] = record[field]
    merged["sector_id"] = sector_id
    merged["last_seen_ts"] = record.get("last_seen_ts") or _now_iso(now)
    return merged


def upsert_sector(world_id, record, state_dir=None, now=None):
    """Write one (possibly partial) sector record into `world_id`'s
    store -- see module docstring for the field-level replace-not-merge
    (and nested-port-merge) semantics. Returns a deep copy of the
    resulting merged sector. ALWAYS a real write under the per-sector
    lock, and ALWAYS re-stamps `last_seen_ts` -- see the module
    docstring's "`last_seen_ts` always advances" section for why an
    earlier true-no-op-skip optimization here was walked back."""
    if "sector_id" not in record:
        raise WorldModelError("upsert_sector: record is missing required 'sector_id' key")
    sector_id = record["sector_id"]

    with _sector_lock(world_id, sector_id, state_dir=state_dir):
        existing = _load_sector_file(world_id, sector_id, state_dir=state_dir)
        merged = _compute_merged_sector(existing, record, now)
        _save_sector_file(world_id, sector_id, merged, state_dir=state_dir)
    return copy.deepcopy(merged)


def bulk_upsert(world_id, records, state_dir=None, now=None):
    """Batch form of `upsert_sector` -- the write path a batch
    port/sector report (many sectors on one screen) or a density-scan
    exploration pass needs. Each record is upserted under its OWN
    per-sector lock (mack Finding 3: a bulk write of N sectors must not
    hold one shared lock across all N -- that would reintroduce the
    exact cross-sector contention per-sector persistence exists to
    remove). Returns a list of deep copies of the merged sectors, in
    the same order as `records`."""
    if not records:
        return []
    return [upsert_sector(world_id, r, state_dir=state_dir, now=now) for r in records]


def write_from_cim_report(world_id, rendered_text, state_dir=None, now=None):
    """Product CIM ingest: ``parse_port_report`` → ``bulk_upsert``.

    WO-WIRE-BULK-UPSERT-CIM-INGEST: this is the product call site for
    ``bulk_upsert``. Callers must already have proven provenance
    (``classify_screen`` → ``cim_report``); this function does not
    re-classify — it only refuses empty/unparseable text by writing
    nothing. Never invents sectors.
    """
    from tw2002_aiclient.session.state_parser import parse_port_report

    if not isinstance(rendered_text, str) or not rendered_text.strip():
        return []
    records = parse_port_report(rendered_text)
    if not records:
        return []
    return bulk_upsert(world_id, records, state_dir=state_dir, now=now)


#: The landmark name recorded for StarDock. A single constant because the
#: store dedups landmarks by `casefold()` but NOT by spelling -- "StarDock"
#: and "Star Dock" would both survive as separate entries, and since
#: `landmarks` unions there is no product path that could ever remove the
#: loser. One name, written from one place.
STARDOCK_LANDMARK = "StarDock"


def add_landmark(world_id, sector_id, name, state_dir=None, now=None):
    """Attribute a named landmark to an EXPLICITLY-SUPPLIED sector.

    The product-facing write path into `landmarks`, and deliberately the
    only one: `write_from_state` refuses to carry landmarks (it maps a raw
    state read, which has no landmark to report), so anything that learns a
    landmark has to say *which sector* it belongs to out loud rather than
    letting a general-purpose write infer it.

    **Caller supplies the sector; this function never guesses it.** That
    division matters more here than elsewhere in this module because
    `landmarks` is the one UNIONING field -- a wrong attribution is not
    overwritten by the next correct write, and there is no removal path
    anywhere in the product. A landmark written into the wrong sector is
    permanent. So the decision "do we know where we are?" belongs to the
    caller that can actually answer it, and arrives here already made.

    Junk RAISES rather than returning a quiet negative. A bad `name` or a
    non-int `sector_id` is a programming error, and if it returned `None`
    it would be indistinguishable from the caller's legitimate "we do not
    know the sector, do not write" -- which is the one signal that must
    stay readable.
    """
    if isinstance(sector_id, bool) or not isinstance(sector_id, int):
        raise WorldModelError(f"add_landmark: sector_id must be an int, got {sector_id!r}")
    if not isinstance(name, str) or not name.strip():
        raise WorldModelError(f"add_landmark: name must be a non-empty str, got {name!r}")
    record = {"sector_id": sector_id, "landmarks": [name]}
    return upsert_sector(world_id, record, state_dir=state_dir, now=now)


def get_sector(world_id, sector_id, state_dir=None):
    """A single sector's record (deep copy -- mutating the return
    value never touches the live store), or `None` if this world has
    never seen that sector."""
    entry = _load_sector_file(world_id, sector_id, state_dir=state_dir)
    return copy.deepcopy(entry) if entry is not None else None


def all_sectors(world_id, state_dir=None):
    """Every known sector in this world, sorted by `sector_id`, as deep
    copies (mutating the returned list/dicts never touches the live
    store). O(total known sectors) by nature (every sector's file must
    be read to list them all) -- unlike `upsert_sector`, this was never
    the hot path mack's Finding 3 targeted."""
    sectors_dir = _sectors_dir(world_id, state_dir=state_dir)
    if not sectors_dir.exists():
        return []
    sector_ids = sorted(int(p.stem) for p in sectors_dir.glob("*.json"))
    return [
        copy.deepcopy(_load_sector_file(world_id, sid, state_dir=state_dir)) for sid in sector_ids
    ]


def known_sector_count(world_id, state_dir=None):
    """How many sectors this world has on file — or `None` when that
    cannot be determined.

    The cheap sibling of `all_sectors`, for callers that want the COUNT
    and nothing else. `all_sectors` reads and deep-copies every sector
    file to produce a list whose length is then thrown away; measured on
    this layout that is ~157ms at 1000 sectors and ~780ms at 5000, while
    counting directory entries is ~5ms and ~26ms. The cockpit's GOALS
    Map row wants only the number, and the launcher's whole-process CPU
    budget (`tests/test_dead_terminal_spin.py`, 0.5s) has no room for
    the list version.

    **`None` is not zero, and the distinction is the point.** A missing
    world directory means no sector has ever been written for this world
    -- genuinely zero known sectors, and reporting that is honest. An
    UNREADABLE directory means we cannot tell, and reporting zero there
    would fabricate "you have explored nothing" out of a permissions
    error. `Path.glob` cannot make that distinction: it swallows
    `PermissionError` and yields nothing, so an unreadable directory and
    an empty one are identical through it. `os.scandir` raises instead,
    which is the only reason it is used here in place of the `glob` its
    neighbours use.

    Counted the way `all_sectors` counts -- entries whose stem is an
    integer -- so the two agree on every store `all_sectors` survives,
    while a stray non-numeric `*.json` is skipped here rather than
    raising `ValueError` as it would there.
    """
    sectors_dir = _sectors_dir(world_id, state_dir=state_dir)
    total = 0
    try:
        with os.scandir(sectors_dir) as entries:
            for entry in entries:
                name = entry.name
                if not name.endswith(".json"):
                    continue
                stem = name[: -len(".json")]
                try:
                    int(stem)
                except ValueError:
                    continue
                total += 1
    except FileNotFoundError:
        return 0
    except OSError:
        return None
    return total


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
    cleared).

    `state_parser.parse_state()` doesn't currently extract a port
    `class` at all -- mack Finding 1: the OLD mapping wrote
    `"class": parsed_port.get("class")`, an explicit `None` on every
    ordinary port visit, which the store's old wholesale-replace `port`
    semantics let CLOBBER a `class` a previous CIM `bulk_upsert` had
    already learned. The fix (generalized per the finding: this mapping
    must never emit an explicit-`None` nested field for something
    merely UNOBSERVED) is to omit the `class` key entirely when
    `parsed_port` doesn't have one -- `_merge_port`'s nested-merge on
    the store side then preserves whatever `class` (if any) is already
    on record, rather than resetting it."""
    sector_id = parsed_state.get("sector")
    if sector_id is None:
        return None

    record = {"sector_id": sector_id}
    if "warps" in parsed_state:
        record["warps"] = list(parsed_state["warps"])
    if "port" in parsed_state:
        # Explicit None = sector-status "Ports : None" (clear prior flyby).
        # A dict may be presence-only (no commodities/class). Only emit
        # nested keys that were actually observed -- an absent
        # `commodities` must NOT write [] and wipe a previously learned
        # commerce-report row list.
        parsed_port = parsed_state["port"]
        if parsed_port is None:
            record["port"] = None
        else:
            port_record = {
                "last_seen_ts": _now_iso(now),
            }
            if "commodities" in parsed_port:
                port_record["commodities"] = [dict(c) for c in parsed_port.get("commodities") or []]
            if "class" in parsed_port:
                port_record["class"] = parsed_port["class"]
            record["port"] = port_record
    if "threats" in parsed_state:
        record["threats"] = dict(parsed_state["threats"])

    merged = upsert_sector(world_id, record, state_dir=state_dir, now=now)
    port_out = record.get("port")
    if isinstance(port_out, dict) and port_out.get("commodities"):
        _record_port_floor_observation(sector_id, port_out, state_dir=state_dir)
    return merged


def write_density_scan(world_id, readings, state_dir=None, now=None):
    """Persist density-scan readings into each sector's ``density_scan`` field.

    ``readings`` is ``{sector_id: density_value}`` from
    :func:`tw2002_aiclient.density_scan.parse_density_scan`. Empty / non-dict
    / junk entries write nothing (fail-closed). Never mutates ``threats`` or
    ``port`` — hypothesis decode stays inside ``density_scan`` so route-hazard
    guards cannot STOP on unverified atoms. Never sends keystrokes.

    Each written object is tagged ``verification: HYPOTHESIS`` until a live
    multi-sector density screen confirms the grammar.
    """
    if not isinstance(readings, dict) or not readings:
        return []
    from tw2002_aiclient.density_scan import (
        decode_density_atoms,
        fighter_presence_hypothesis,
    )

    written = []
    for sector_id, density in readings.items():
        if isinstance(sector_id, bool) or not isinstance(sector_id, int):
            continue
        if sector_id <= 0:
            continue
        if isinstance(density, bool) or not isinstance(density, int) or density < 0:
            continue
        atoms = decode_density_atoms(density)
        fighter = fighter_presence_hypothesis(density)
        payload = {
            "value": density,
            "atoms": list(atoms),
            "verification": DENSITY_SCAN_VERIFICATION,
            "source": "density_scan",
        }
        if fighter is not None:
            payload["fighter_presence"] = fighter
        merged = upsert_sector(
            world_id,
            {"sector_id": sector_id, "density_scan": payload},
            state_dir=state_dir,
            now=now,
        )
        written.append(merged)
    return written


def write_port_only(world_id, sector_id, parsed_port, state_dir=None, now=None):
    """WO-FA2b write path: persist JUST a sector's `port` field, for an
    EXPLICITLY-SUPPLIED `sector_id` -- the docked commerce-report case
    `write_from_state()` can't handle, because the screen that observed
    the port commodities carries no "Sector : N" line of its own to
    derive a sector from. The caller
    (`session.sector_explore._ingest_docked_report`) resolves `sector_id`
    from `state_parser.read_current_sector()` -- THIS SAME SCREEN's own
    trailing ship Command prompt (WO-FA2b REVISE: an earlier design
    anchored to a cross-screen `session.last_genuine_sector` instead, but
    pyte's lack of scrollback could let a long warp-then-dock burst scroll
    the sector-status line off the settled grid before that anchor was
    ever set).

    **Docstring corrected 2026-07-28 (WO-EXPLORE-DOCK-NEW-PORT).** Until
    that WO this function had NO product caller, and the three symbols
    this paragraph originally named -- `protocol._write_world_model`,
    `state_parser.is_genuine_port_report`,
    `state_parser.sector_from_command_prompt` -- had no definition
    anywhere in the tree. Neither did `parse_state`, whose "existing
    commodity extraction" both this docstring and canon's Ingestion
    section described as merely being reused. So this writer shipped
    fully tested as a consumer of a shape nothing produced, while its
    documentation read as though the path were wired. The producer is
    now `state_parser.read_port_commodities_from_report`, and it is THE
    one -- canon's "never write a second row parser" is a live constraint
    on the next caller, not a description of a parser that never existed.

    `parsed_port` is that reader's output in canon's vocab shape
    (`{"commodities": [{name, status, amount, pct}]}` -- see
    world-model.md's Schema table) -- never re-derived or re-parsed here.

    Only `commodities`/`last_seen_ts` are ever written to the `port`
    sub-dict -- same as `write_from_state`'s own port mapping, and for
    the same reason: a plain screen visit (docked or in-sector) never
    observes a port's `class` at all, so this never supplies that
    sub-key, letting `upsert_sector`'s nested `_merge_port` (mack
    Finding 1) preserve whatever `class` a previous CIM `bulk_upsert`
    already learned for this sector rather than clobbering it with an
    explicit `None`. `warps`/`threats` are similarly untouched (absent
    from `record` entirely) -- field-level upsert semantics preserve
    whatever's already stored for this sector; a docked port visit says
    nothing about either."""
    port_record = {
        "commodities": [dict(c) for c in parsed_port.get("commodities", [])],
        "last_seen_ts": _now_iso(now),
    }
    record = {"sector_id": sector_id, "port": port_record}
    merged = upsert_sector(world_id, record, state_dir=state_dir, now=now)
    if port_record.get("commodities"):
        _record_port_floor_observation(sector_id, port_record, state_dir=state_dir)
    return merged


def _record_port_floor_observation(sector_id, port_dict, *, state_dir=None):
    """Best-effort append to the port-floor observation JSONL (WO capture loop).

    Never raises — world_model writes must not fail because the capture
    store is missing or unwritable. ``traded_since_prior`` stays unknown
    here; only an operator/ledger-aware caller can set False/True.
    """
    try:
        from tw2002_aiclient.port_floor_capture import record_port_write

        record_port_write(sector_id, port_dict, state_dir=state_dir)
    except Exception:
        return
