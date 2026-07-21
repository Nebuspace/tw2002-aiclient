"""World model tests (TW-06) -- no network, tmp_path only, never
touches the real state/ directory.

2026-07-19 hardening pass (mack adversarial review, findings 1/3):
the persistence layout changed from one `sectors.json` per world to
one `<sector_id>.json` file per sector (Finding 3b -- O(1) writes +
per-sector lock scope instead of an O(total sectors) full-store
rewrite behind one world-wide lock). `load_store`/`save_store`/
`_store_lock`/`_store_path` were internal-only (never part of the
documented public API: get_sector/upsert_sector/bulk_upsert/
all_sectors/query/write_from_state) and are GONE -- replaced by
`_load_sector_file`/`_save_sector_file`/`_sector_lock`/`_sector_path`,
scoped per sector rather than per world. Tests below that exercised
those internals directly are rewritten against the new primitives;
tests exercising only the public API are unchanged. This was a
greenfield change (no `state/world/` data existed anywhere yet) -- no
migration was needed or attempted."""

import datetime
import fcntl
import json
import os
import stat
import threading
import time

import pytest

from twclient import world_model


WORLD_A = "hostA__F__ALPHA"
WORLD_B = "hostB__F__BRAVO"


# -- per-sector file load/save (replaces the old whole-store load_store/
# save_store direct tests) ---------------------------------------------

def test_load_sector_file_missing_returns_none(tmp_path):
    assert world_model._load_sector_file(WORLD_A, 1, state_dir=tmp_path) is None
    assert not (tmp_path / WORLD_A / "sectors" / "1.json").exists()  # reading never creates the file


def test_save_then_load_sector_file_round_trips(tmp_path):
    record = world_model._default_sector(1)
    world_model._save_sector_file(WORLD_A, 1, record, state_dir=tmp_path)
    assert world_model._load_sector_file(WORLD_A, 1, state_dir=tmp_path) == record


def test_save_sector_file_leaves_no_temp_file_after_success(tmp_path):
    world_model._save_sector_file(WORLD_A, 1, world_model._default_sector(1), state_dir=tmp_path)
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert path.exists()


def test_save_sector_file_creates_file_with_0600_permissions(tmp_path):
    world_model._save_sector_file(WORLD_A, 1, world_model._default_sector(1), state_dir=tmp_path)
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_upsert_sector_atomic_write_survives_a_crash_before_rename(tmp_path, monkeypatch):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [1]}, state_dir=tmp_path)
    original = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)

    def boom(*_a, **_kw):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(world_model.os, "replace", boom)

    with pytest.raises(OSError):
        world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)

    assert world_model.get_sector(WORLD_A, 1, state_dir=tmp_path) == original


def test_upsert_sector_removes_orphaned_tmp_file_on_write_failure(tmp_path, monkeypatch):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [1]}, state_dir=tmp_path)
    original = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)

    def boom(*_a, **_kw):
        raise ValueError("simulated write-time failure")

    monkeypatch.setattr(world_model.json, "dump", boom)

    with pytest.raises(ValueError):
        world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)

    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert world_model.get_sector(WORLD_A, 1, state_dir=tmp_path) == original


# -- corrupt/malformed sector files -------------------------------------

def test_load_sector_file_raises_on_truncated_json(tmp_path):
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"sector_id": 1,', encoding="utf-8")
    with pytest.raises(world_model.WorldModelError):
        world_model._load_sector_file(WORLD_A, 1, state_dir=tmp_path)


def test_load_sector_file_raises_on_empty_file(tmp_path):
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    with pytest.raises(world_model.WorldModelError):
        world_model._load_sector_file(WORLD_A, 1, state_dir=tmp_path)


def test_load_sector_file_raises_on_non_object_shape(tmp_path):
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(world_model.WorldModelError):
        world_model._load_sector_file(WORLD_A, 1, state_dir=tmp_path)


def test_load_sector_file_raises_on_missing_sector_id(tmp_path):
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"warps": []}), encoding="utf-8")
    with pytest.raises(world_model.WorldModelError):
        world_model._load_sector_file(WORLD_A, 1, state_dir=tmp_path)


def test_a_corrupt_sector_does_not_block_a_DIFFERENT_sector(tmp_path):
    """Per-sector granularity means a corrupt sector 1 must not prevent
    reading/writing a perfectly healthy sector 2 -- a direct consequence
    of Finding 3b's per-file layout (the old single-store design had no
    such isolation: one corrupt entry anywhere failed the ENTIRE load)."""
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")

    world_model.upsert_sector(WORLD_A, {"sector_id": 2, "warps": [3]}, state_dir=tmp_path)
    assert world_model.get_sector(WORLD_A, 2, state_dir=tmp_path)["warps"] == [3]

    with pytest.raises(world_model.WorldModelError):
        world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)


# -- upsert_sector / get_sector round trip -----------------------------------

def test_upsert_then_get_round_trips(tmp_path):
    record = {"sector_id": 42, "warps": [41, 43], "landmarks": ["stardock"]}
    merged = world_model.upsert_sector(WORLD_A, record, state_dir=tmp_path)

    assert merged["sector_id"] == 42
    assert merged["warps"] == [41, 43]
    assert merged["landmarks"] == ["stardock"]
    assert merged["last_seen_ts"] is not None

    fetched = world_model.get_sector(WORLD_A, 42, state_dir=tmp_path)
    assert fetched == merged


def test_get_sector_returns_none_for_unknown_sector(tmp_path):
    assert world_model.get_sector(WORLD_A, 999, state_dir=tmp_path) is None


def test_upsert_sector_defaults_unspecified_fields_on_first_write(tmp_path):
    merged = world_model.upsert_sector(WORLD_A, {"sector_id": 7}, state_dir=tmp_path)
    assert merged["warps"] == []
    assert merged["port"] is None
    assert merged["threats"] == {"mines": False, "fighters": None}
    assert merged["landmarks"] == []
    assert merged["formation_membership"] is None


def test_upsert_sector_requires_sector_id(tmp_path):
    with pytest.raises(world_model.WorldModelError):
        world_model.upsert_sector(WORLD_A, {"warps": [1, 2]}, state_dir=tmp_path)


def test_get_sector_returns_a_copy_not_a_live_reference(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)
    fetched = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)
    fetched["warps"].append(999)

    fresh = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)
    assert fresh["warps"] == [2]


# -- supersede-not-merge (field-level replace) -------------------------------

def test_second_write_to_same_field_supersedes_rather_than_merging(tmp_path):
    """The canon's explicit rule: a later write to the same sector
    supersedes the earlier one rather than merging stale and fresh data
    -- an old commodities list must never get unioned with a new one."""
    world_model.upsert_sector(
        WORLD_A,
        {
            "sector_id": 5,
            "port": {"class": "BBS", "commodities": [{"name": "Fuel Ore", "status": "selling", "amount": 100, "pct": 50}]},
        },
        state_dir=tmp_path,
    )
    merged = world_model.upsert_sector(
        WORLD_A,
        {
            "sector_id": 5,
            "port": {"class": "BBS", "commodities": [{"name": "Equipment", "status": "buying", "amount": 500, "pct": 10}]},
        },
        state_dir=tmp_path,
    )

    # the new port value REPLACES the old one wholesale -- Fuel Ore is gone,
    # not unioned alongside Equipment.
    assert merged["port"]["commodities"] == [
        {"name": "Equipment", "status": "buying", "amount": 500, "pct": 10}
    ]


def test_a_field_absent_from_the_write_is_preserved_not_cleared(tmp_path):
    """The "additive" half of the same rule: a write that doesn't touch
    `port` at all (e.g. a warps-only movement update) must not erase
    previously-learned port data for that sector."""
    world_model.upsert_sector(
        WORLD_A,
        {"sector_id": 5, "port": {"class": "BBS", "commodities": []}},
        state_dir=tmp_path,
    )
    merged = world_model.upsert_sector(
        WORLD_A, {"sector_id": 5, "warps": [4, 6]}, state_dir=tmp_path
    )

    assert merged["warps"] == [4, 6]
    assert merged["port"] == {"class": "BBS", "commodities": []}  # untouched


def test_upsert_sector_always_restamps_last_seen_ts(tmp_path):
    """An EXPLICIT caller-supplied last_seen_ts is real content (a
    deliberate re-stamp), not the auto-generated fallback the Finding 3a
    dedup check excludes -- so two explicit, DIFFERENT stamps must both
    persist even though nothing else about the record changed."""
    first = world_model.upsert_sector(
        WORLD_A, {"sector_id": 1, "last_seen_ts": "2026-07-18T00:00:00Z"}, state_dir=tmp_path
    )
    second = world_model.upsert_sector(
        WORLD_A, {"sector_id": 1, "last_seen_ts": "2026-07-19T00:00:00Z"}, state_dir=tmp_path
    )
    assert first["last_seen_ts"] == "2026-07-18T00:00:00Z"
    assert second["last_seen_ts"] == "2026-07-19T00:00:00Z"


# -- nested port field-level merge (mack Finding 1) --------------------------

def test_write_from_state_class_unobserved_preserves_a_previously_cim_learned_class(tmp_path):
    """Adapted from mack's probe_clobber.py: a CIM bulk_upsert teaches
    sector 100's port class is BBS; an ordinary later port-trade-screen
    visit through write_from_state() (parse_state() never extracts a
    class at all) must NOT clobber it back to None -- the class simply
    isn't part of what that screen observed, so it must be preserved,
    not overwritten with an explicit None."""
    world_model.bulk_upsert(
        WORLD_A,
        [{"sector_id": 100, "port": {"class": "BBS", "commodities": [
            {"name": "Fuel Ore", "status": "buying", "pct": 50}
        ]}}],
        state_dir=tmp_path,
    )
    before = world_model.get_sector(WORLD_A, 100, state_dir=tmp_path)
    assert before["port"]["class"] == "BBS"

    parsed_state = {
        "sector": 100,
        "port": {"commodities": [
            {"name": "Fuel Ore", "status": "buying", "amount": 500, "pct": 55},
        ]},
    }
    world_model.write_from_state(WORLD_A, parsed_state, state_dir=tmp_path)

    after = world_model.get_sector(WORLD_A, 100, state_dir=tmp_path)
    assert after["port"]["class"] == "BBS", "an unobserved class must never clobber a previously-learned one"
    assert after["port"]["commodities"][0]["pct"] == 55  # the actually-observed field DID update


def test_upsert_sector_explicit_none_class_still_resets_it(tmp_path):
    """The nested merge only preserves ABSENT sub-keys -- a caller that
    explicitly supplies `"class": None` (as opposed to omitting the key)
    is making a deliberate statement and must still win, exactly like
    any other present-field-replaces case."""
    world_model.upsert_sector(
        WORLD_A, {"sector_id": 5, "port": {"class": "BBS", "commodities": []}}, state_dir=tmp_path
    )
    merged = world_model.upsert_sector(
        WORLD_A, {"sector_id": 5, "port": {"class": None, "commodities": []}}, state_dir=tmp_path
    )
    assert merged["port"]["class"] is None


def test_upsert_sector_explicit_none_port_still_resets_the_whole_field(tmp_path):
    """An explicit top-level `"port": None` (the whole field, not a
    partial dict) is a deliberate "no port here" reset -- NOT run
    through the nested per-sub-field merge, same as any other top-level
    field's explicit-value-present case."""
    world_model.upsert_sector(
        WORLD_A, {"sector_id": 5, "port": {"class": "BBS", "commodities": []}}, state_dir=tmp_path
    )
    merged = world_model.upsert_sector(WORLD_A, {"sector_id": 5, "port": None}, state_dir=tmp_path)
    assert merged["port"] is None


# -- bulk_upsert --------------------------------------------------------------

def test_bulk_upsert_writes_many_sectors_in_one_pass(tmp_path):
    records = [{"sector_id": i, "warps": [i - 1, i + 1]} for i in range(1, 6)]
    merged_list = world_model.bulk_upsert(WORLD_A, records, state_dir=tmp_path)

    assert [m["sector_id"] for m in merged_list] == [1, 2, 3, 4, 5]
    all_sectors = world_model.all_sectors(WORLD_A, state_dir=tmp_path)
    assert len(all_sectors) == 5
    assert {s["sector_id"] for s in all_sectors} == {1, 2, 3, 4, 5}


def test_bulk_upsert_empty_list_is_a_noop(tmp_path):
    result = world_model.bulk_upsert(WORLD_A, [], state_dir=tmp_path)
    assert result == []
    assert not (tmp_path / WORLD_A).exists()


def test_bulk_upsert_acquires_one_lock_per_new_sector_not_a_shared_lock(tmp_path, monkeypatch):
    """mack Finding 3b: a bulk write of N sectors must NOT hold one
    shared lock across all N (that would reintroduce the exact
    cross-sector contention per-sector persistence exists to remove).
    Proves the opposite of the old single-store design's guarantee: N
    distinct new sectors acquire N distinct per-sector locks, one each
    -- never fewer (no accidental sharing) and never more (no redundant
    re-locking)."""
    acquired = []
    real_sector_lock = world_model._sector_lock

    def counting_lock(world_id, sector_id, state_dir=None):
        acquired.append(sector_id)
        return real_sector_lock(world_id, sector_id, state_dir=state_dir)

    monkeypatch.setattr(world_model, "_sector_lock", counting_lock)
    records = [{"sector_id": i} for i in range(1, 11)]
    world_model.bulk_upsert(WORLD_A, records, state_dir=tmp_path)
    assert sorted(acquired) == list(range(1, 11))


# -- all_sectors / query --------------------------------------------------------

def test_all_sectors_returns_sorted_by_sector_id(tmp_path):
    for sid in (30, 1, 15):
        world_model.upsert_sector(WORLD_A, {"sector_id": sid}, state_dir=tmp_path)
    sector_ids = [s["sector_id"] for s in world_model.all_sectors(WORLD_A, state_dir=tmp_path)]
    assert sector_ids == [1, 15, 30]


def test_all_sectors_returns_copies_not_live_references(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "landmarks": ["stardock"]}, state_dir=tmp_path)
    sectors = world_model.all_sectors(WORLD_A, state_dir=tmp_path)
    sectors[0]["landmarks"].append("mutated")

    fresh = world_model.all_sectors(WORLD_A, state_dir=tmp_path)
    assert fresh[0]["landmarks"] == ["stardock"]


def test_query_filters_by_predicate(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "threats": {"mines": True, "fighters": None}}, state_dir=tmp_path)
    world_model.upsert_sector(WORLD_A, {"sector_id": 2, "threats": {"mines": False, "fighters": None}}, state_dir=tmp_path)

    mined = world_model.query(WORLD_A, lambda s: s["threats"]["mines"], state_dir=tmp_path)
    assert [s["sector_id"] for s in mined] == [1]


# -- cross-world isolation (load-bearing) ------------------------------------

def test_two_worlds_never_share_sector_data(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 5, "landmarks": ["stardock"]}, state_dir=tmp_path)

    # world B has never seen sector 5 at all.
    assert world_model.get_sector(WORLD_B, 5, state_dir=tmp_path) is None
    assert world_model.all_sectors(WORLD_B, state_dir=tmp_path) == []

    # writing sector 5 into world B doesn't touch world A's copy.
    world_model.upsert_sector(WORLD_B, {"sector_id": 5, "landmarks": ["class_zero"]}, state_dir=tmp_path)
    assert world_model.get_sector(WORLD_A, 5, state_dir=tmp_path)["landmarks"] == ["stardock"]
    assert world_model.get_sector(WORLD_B, 5, state_dir=tmp_path)["landmarks"] == ["class_zero"]


def test_two_worlds_persist_to_distinct_sector_directories(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1}, state_dir=tmp_path)
    world_model.upsert_sector(WORLD_B, {"sector_id": 1}, state_dir=tmp_path)
    path_a = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    path_b = world_model._sector_path(WORLD_B, 1, state_dir=tmp_path)
    assert path_a.exists()
    assert path_b.exists()
    assert path_a != path_b


# -- write_from_state mapping -------------------------------------------------

def test_write_from_state_with_no_sector_field_is_a_noop(tmp_path):
    result = world_model.write_from_state(WORLD_A, {"credits": 100}, state_dir=tmp_path)
    assert result is None
    assert world_model.all_sectors(WORLD_A, state_dir=tmp_path) == []


def test_write_from_state_maps_sector_and_warps(tmp_path):
    parsed = {"sector": 42, "warps": [41, 43], "credits": 500}
    merged = world_model.write_from_state(WORLD_A, parsed, state_dir=tmp_path)
    assert merged["sector_id"] == 42
    assert merged["warps"] == [41, 43]


def test_write_from_state_maps_port_commodities(tmp_path):
    parsed = {
        "sector": 42,
        "port": {"commodities": [{"name": "Fuel Ore", "status": "selling", "amount": 18000, "pct": 100}]},
    }
    merged = world_model.write_from_state(WORLD_A, parsed, state_dir=tmp_path)
    assert merged["port"]["commodities"] == [
        {"name": "Fuel Ore", "status": "selling", "amount": 18000, "pct": 100}
    ]
    assert merged["port"]["class"] is None  # state_parser doesn't extract class today, nothing to preserve yet
    assert merged["port"]["last_seen_ts"] is not None


def test_write_from_state_without_port_key_preserves_previously_known_port(tmp_path):
    world_model.write_from_state(
        WORLD_A,
        {"sector": 42, "port": {"commodities": [{"name": "Equipment", "status": "buying", "amount": 1, "pct": 1}]}},
        state_dir=tmp_path,
    )
    # a later parse of the same sector with no port info on screen (e.g. after
    # warping away) must not wipe the port info already learned.
    merged = world_model.write_from_state(WORLD_A, {"sector": 42, "warps": [41]}, state_dir=tmp_path)
    assert merged["port"]["commodities"][0]["name"] == "Equipment"


def test_write_from_state_actually_persists(tmp_path):
    world_model.write_from_state(WORLD_A, {"sector": 7}, state_dir=tmp_path)
    assert world_model.get_sector(WORLD_A, 7, state_dir=tmp_path) is not None


# -- last_seen_ts always advances (Samantha's 2026-07-19 ruling, -----------
# -- supersedes mack Finding 3a's true no-op-skip dedup) --------------------
#
# An earlier hardening pass made upsert_sector() skip the lock and the
# disk write entirely when the merge was a content no-op, to cut write
# volume. That silently froze last_seen_ts on a genuine, unchanged
# re-observation -- wrong, since it's the "I was actually here, this
# recently" staleness marker a future freshness/rescan policy needs to
# stay honest. Per-sector writes are already O(1)/~1ms, so the removed
# skip's benefit was marginal next to that correctness cost. Every
# upsert_sector() call now always writes and always re-stamps
# last_seen_ts.


def test_upsert_sector_identical_content_still_writes_and_advances_last_seen_ts(tmp_path, monkeypatch):
    """Adapted from mack's probe_ts_semantics.py: re-observing the SAME
    sector with IDENTICAL content, at a later clock reading, must still
    acquire the lock, still rewrite the file, and still advance
    last_seen_ts -- the opposite of the old dedup no-op's guarantee."""
    clock1 = lambda: datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    clock2 = lambda: datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)

    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [2, 3]}, state_dir=tmp_path, now=clock1)
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    mtime_before = path.stat().st_mtime_ns
    first = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)

    lock_calls = []
    real_sector_lock = world_model._sector_lock

    def counting_lock(world_id, sector_id, state_dir=None):
        lock_calls.append(sector_id)
        return real_sector_lock(world_id, sector_id, state_dir=state_dir)

    monkeypatch.setattr(world_model, "_sector_lock", counting_lock)
    merged = world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [2, 3]}, state_dir=tmp_path, now=clock2)

    assert lock_calls == [1], "a genuine re-observation must still acquire the lock and write"
    assert path.stat().st_mtime_ns != mtime_before, "a genuine re-observation must still rewrite the file"
    assert merged["warps"] == [2, 3]
    assert merged["last_seen_ts"] != first["last_seen_ts"], (
        "last_seen_ts must advance on a genuine re-observation, even with unchanged content"
    )
    assert merged["last_seen_ts"] == world_model._now_iso(clock2)


def test_upsert_sector_changed_content_still_writes(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [2, 3]}, state_dir=tmp_path)
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    mtime_before = path.stat().st_mtime_ns
    time.sleep(0.01)

    merged = world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": [4, 5]}, state_dir=tmp_path)

    assert path.stat().st_mtime_ns != mtime_before
    assert merged["warps"] == [4, 5]


def test_write_from_state_repeated_identical_observation_still_advances_last_seen_ts(tmp_path):
    """The real hot-path shape: write_from_state() never supplies an
    explicit last_seen_ts (top-level OR nested port.last_seen_ts) --
    both are auto-stamped fresh on every call. Re-observing the exact
    same port/warps twice in a row must still re-stamp both, at a later
    clock reading."""
    clock1 = lambda: datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    clock2 = lambda: datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
    parsed = {
        "sector": 1,
        "warps": [2, 3],
        "port": {"commodities": [{"name": "Fuel Ore", "status": "buying", "amount": 10, "pct": 50}]},
    }
    world_model.write_from_state(WORLD_A, parsed, state_dir=tmp_path, now=clock1)
    first = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)

    world_model.write_from_state(WORLD_A, dict(parsed), state_dir=tmp_path, now=clock2)
    second = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)

    assert second["last_seen_ts"] != first["last_seen_ts"]
    assert second["port"]["last_seen_ts"] != first["port"]["last_seen_ts"]


def test_bulk_upsert_repeat_batch_still_writes_and_advances_timestamps(tmp_path):
    clock1 = lambda: datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    clock2 = lambda: datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
    records = [{"sector_id": i, "warps": [i + 1]} for i in range(1, 6)]
    world_model.bulk_upsert(WORLD_A, records, state_dir=tmp_path, now=clock1)
    before = {i: world_model.get_sector(WORLD_A, i, state_dir=tmp_path)["last_seen_ts"] for i in range(1, 6)}

    world_model.bulk_upsert(WORLD_A, [dict(r) for r in records], state_dir=tmp_path, now=clock2)
    after = {i: world_model.get_sector(WORLD_A, i, state_dir=tmp_path)["last_seen_ts"] for i in range(1, 6)}

    assert all(after[i] != before[i] for i in range(1, 6))


# -- write_port_only mapping (WO-FA2b docked-port write path) ---------------
#
# The docked commerce-report case: the SCREEN carries no sector of its
# own, so the caller (protocol._write_world_model) resolves `sector_id`
# externally (state_parser.sector_from_command_prompt(), WO-FA2b REVISE --
# this SAME screen's own trailing Command prompt, not a cross-screen
# anchor) and hands it in explicitly, rather than write_port_only deriving
# one the way write_from_state() derives it from parsed_state["sector"].


def test_write_port_only_writes_commodities_to_the_explicit_sector(tmp_path):
    parsed_port = {
        "commodities": [
            {"name": "Fuel Ore", "status": "buying", "amount": 2850, "pct": 100},
            {"name": "Organics", "status": "buying", "amount": 930, "pct": 100},
            {"name": "Equipment", "status": "buying", "amount": 2720, "pct": 100},
        ]
    }
    merged = world_model.write_port_only(WORLD_A, 4309, parsed_port, state_dir=tmp_path)
    assert merged["sector_id"] == 4309
    assert merged["port"]["commodities"] == parsed_port["commodities"]
    assert merged["port"]["last_seen_ts"] is not None


def test_write_port_only_never_touches_warps_or_threats_for_the_sector(tmp_path):
    """A docked port visit observes nothing about warps/threats -- an
    already-known warps list (from an earlier sector-status visit, or a
    CIM bulk_upsert) must survive untouched, same field-level upsert
    semantics as write_from_state()."""
    world_model.upsert_sector(WORLD_A, {"sector_id": 4309, "warps": [4308, 4310]}, state_dir=tmp_path)
    world_model.write_port_only(
        WORLD_A, 4309, {"commodities": [{"name": "Fuel Ore", "status": "buying", "amount": 1, "pct": 1}]},
        state_dir=tmp_path,
    )
    merged = world_model.get_sector(WORLD_A, 4309, state_dir=tmp_path)
    assert merged["warps"] == [4308, 4310]


def test_write_port_only_never_clobbers_a_previously_cim_learned_class(tmp_path):
    """Mirrors write_from_state's own mack-Finding-1 guarantee: a class
    already learned via a CIM bulk_upsert must survive a later docked
    visit that (like every ordinary screen visit) never observes
    `class` at all."""
    world_model.bulk_upsert(
        WORLD_A,
        [{"sector_id": 4309, "port": {"class": "BBB", "commodities": []}}],
        state_dir=tmp_path,
    )
    merged = world_model.write_port_only(
        WORLD_A,
        4309,
        {"commodities": [{"name": "Fuel Ore", "status": "buying", "amount": 2850, "pct": 100}]},
        state_dir=tmp_path,
    )
    assert merged["port"]["class"] == "BBB", "an unobserved class must never be clobbered by a docked-only write"
    assert merged["port"]["commodities"][0]["name"] == "Fuel Ore"


def test_write_port_only_actually_persists(tmp_path):
    world_model.write_port_only(WORLD_A, 4309, {"commodities": []}, state_dir=tmp_path)
    assert world_model.get_sector(WORLD_A, 4309, state_dir=tmp_path) is not None


# -- per-sector hot path (mack Finding 3b: O(1), not O(total sectors)) -------

def test_single_sector_upsert_cost_does_not_grow_with_total_known_sectors(tmp_path):
    """Adapted from mack's probe_hotpath.py: seed worlds of increasing
    known-sector counts, then time ONE incremental upsert to a
    DIFFERENT, unrelated sector in each. Per-sector files mean this cost
    must stay flat -- the old one-big-JSON-file design made it grow
    with total sectors (a full load+rewrite on every write)."""
    timings = {}
    for n in (50, 400, 1500):
        wid = f"scale_world_{n}"
        records = [{"sector_id": i, "warps": [i + 1, i - 1]} for i in range(1, n + 1)]
        world_model.bulk_upsert(wid, records, state_dir=tmp_path)

        start = time.perf_counter()
        for _ in range(20):
            world_model.upsert_sector(wid, {"sector_id": 1, "warps": [2, 999]}, state_dir=tmp_path)
            # alternate the value so the dedup no-op path (Finding 3a)
            # doesn't mask what an ACTUAL write costs -- this is timing
            # the write path itself, not the no-op short-circuit.
            world_model.upsert_sector(wid, {"sector_id": 1, "warps": [3, 998]}, state_dir=tmp_path)
        timings[n] = (time.perf_counter() - start) / 40

    # Generous bound: the smallest-world timing scaled up should still
    # comfortably cover the largest-world timing if cost is flat; a
    # real O(n) regression (the old design) would blow this out by
    # 30x at n=1500 vs n=50.
    assert timings[1500] < timings[50] * 8 + 0.02, (
        f"single-sector upsert cost grew with total known sectors: {timings}"
    )


def test_all_sectors_still_lists_every_sector_at_scale(tmp_path):
    """Sanity check alongside the hot-path proof above -- the O(1) write
    path must not have silently broken enumeration."""
    n = 250
    records = [{"sector_id": i} for i in range(1, n + 1)]
    world_model.bulk_upsert(WORLD_A, records, state_dir=tmp_path)
    assert len(world_model.all_sectors(WORLD_A, state_dir=tmp_path)) == n


# -- concurrency: per-sector lock scope removes cross-sector contention -----

def test_sector_lock_real_flock_blocks_second_acquirer_until_released(tmp_path):
    """Real flock proof -- no monkeypatch, no threads: a second, wholly
    independent open-file-description on the SAME sector's lock path
    cannot take LOCK_EX while the first holds it, and can immediately
    after the first releases."""
    path = world_model._sector_path(WORLD_A, 1, state_dir=tmp_path)
    lock_path = world_model._lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fd1 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd1, fcntl.LOCK_EX)
    try:
        fd2 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd2)
    finally:
        fcntl.flock(fd1, fcntl.LOCK_UN)
        os.close(fd1)

    fd3 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd3, fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise now
        fcntl.flock(fd3, fcntl.LOCK_UN)
    finally:
        os.close(fd3)


def test_concurrent_writes_to_different_sectors_do_not_serialize(tmp_path):
    """Adapted from mack's probe_contention.py: the ROOT bug this
    (alongside dedup) exists to fix -- a slow writer holding sector 1's
    lock must NOT stall a concurrent writer touching sector 2. Under the
    old single-store design, every writer shared ONE lock regardless of
    which sector it touched, so this would have blocked for the full
    hold duration; under per-sector locks, sector 2's write proceeds
    immediately."""
    hold_seconds = 1.0

    def slow_writer_on_sector_1():
        with world_model._sector_lock(WORLD_A, 1, state_dir=tmp_path):
            time.sleep(hold_seconds)

    t = threading.Thread(target=slow_writer_on_sector_1)
    t.start()
    time.sleep(0.1)  # let the slow writer acquire sector 1's lock first

    start = time.perf_counter()
    world_model.upsert_sector(WORLD_A, {"sector_id": 2, "warps": [1]}, state_dir=tmp_path)
    elapsed = time.perf_counter() - start
    t.join()

    assert elapsed < hold_seconds * 0.5, (
        f"a concurrent writer on a DIFFERENT sector was stalled {elapsed:.2f}s by a "
        f"{hold_seconds:.2f}s hold on an unrelated sector's lock -- cross-sector contention regressed"
    )


def test_concurrent_upsert_to_the_same_sector_never_loses_an_update(tmp_path, monkeypatch):
    """Same-sector concurrency still needs the lock for correctness --
    per-sector persistence only removes CROSS-sector contention, never
    the within-sector critical section. Two real threads race a write
    to the SAME sector; a monkeypatch hook pauses the first writer
    mid-critical-section (still holding the real flock) so the second
    writer's own lock acquisition is forced to actually block until
    release, proving neither update is silently lost."""
    real_save = world_model._save_sector_file
    first_holding = threading.Event()
    release_first = threading.Event()

    def hook(world_id, sector_id, record, state_dir=None):
        if record.get("warps") == [111]:
            first_holding.set()
            assert release_first.wait(timeout=5), "test deadlocked waiting for release"
        return real_save(world_id, sector_id, record, state_dir=state_dir)

    monkeypatch.setattr(world_model, "_save_sector_file", hook)

    errors = []

    def write(warps):
        try:
            world_model.upsert_sector(WORLD_A, {"sector_id": 1, "warps": warps}, state_dir=tmp_path)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=write, args=([111],))
    t2 = threading.Thread(target=write, args=([222],))

    t1.start()
    assert first_holding.wait(timeout=5), "first writer never reached its critical section"
    t2.start()
    time.sleep(0.2)  # give the second writer a real chance to attempt (and block on) the lock
    release_first.set()

    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not errors, f"unexpected error(s) from concurrent same-sector upsert: {errors}"
    final = world_model.get_sector(WORLD_A, 1, state_dir=tmp_path)
    assert final["warps"] in ([111], [222]), "one of the two racing writers must win outright, not blend"


def test_real_concurrent_upsert_across_many_threads_never_loses_an_update(tmp_path):
    """The acceptance bar (mirrors player_bank's real-writer test): N
    real threads hammering the real public API against ONE shared world
    store at the same instant (a `threading.Barrier` maximizes overlap),
    each writing a DIFFERENT sector. The per-sector lock must guarantee
    zero lost updates regardless of how the OS actually schedules
    them."""
    n = 16
    errors = []
    barrier = threading.Barrier(n)

    def worker(sector_id):
        try:
            barrier.wait(timeout=5)
            world_model.upsert_sector(WORLD_A, {"sector_id": sector_id, "warps": [sector_id]}, state_dir=tmp_path)
        except Exception as e:
            errors.append((sector_id, e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected error(s) from real concurrent upsert_sector: {errors}"
    sector_ids = {s["sector_id"] for s in world_model.all_sectors(WORLD_A, state_dir=tmp_path)}
    assert sector_ids == set(range(n)), (
        f"lost update(s) under real concurrency -- expected {n} sectors, "
        f"got {len(sector_ids)}: missing {set(range(n)) - sector_ids}"
    )


# -- real project paths are never touched by these tests -------------------------

def test_module_level_paths_are_under_the_real_gitignored_state_dir():
    """Sanity check on the constants themselves -- doesn't touch disk."""
    assert world_model.STATE_DIR.name == "state"
    assert world_model.WORLD_DIR.parent == world_model.STATE_DIR
    assert world_model.WORLD_DIR.name == "world"


def test_write_from_state_flyby_presence_sets_port_without_wiping_commodities(tmp_path):
    """Presence-only flyby must not emit commodities=[] and clobber a prior docked read."""
    world_model.write_from_state(
        WORLD_A,
        {"sector": 42, "port": {"commodities": [{"name": "Equipment", "status": "buying", "amount": 1, "pct": 1}]}},
        state_dir=tmp_path,
    )
    merged = world_model.write_from_state(
        WORLD_A,
        {"sector": 42, "port": {"class": "BSB"}},
        state_dir=tmp_path,
    )
    assert merged["port"] is not None
    assert merged["port"]["class"] == "BSB"
    assert merged["port"]["commodities"][0]["name"] == "Equipment"


def test_write_from_state_flyby_empty_presence_creates_port(tmp_path):
    merged = world_model.write_from_state(
        WORLD_A, {"sector": 7, "port": {}}, state_dir=tmp_path,
    )
    assert merged["port"] is not None
    assert merged["port"]["class"] is None
