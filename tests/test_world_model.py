"""World model tests (TW-06) -- no network, tmp_path only, never
touches the real state/ directory."""

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


# -- load_store / save_store ------------------------------------------------

def test_load_store_missing_file_returns_fresh_empty_store(tmp_path):
    store = world_model.load_store(WORLD_A, state_dir=tmp_path)
    assert store == {"version": 1, "world_id": WORLD_A, "sectors": {}}
    assert not (tmp_path / WORLD_A / "sectors.json").exists()  # load never creates the file


def test_save_then_load_round_trips(tmp_path):
    original = {"version": 1, "world_id": WORLD_A, "sectors": {}}
    world_model.save_store(original, WORLD_A, state_dir=tmp_path)
    assert world_model.load_store(WORLD_A, state_dir=tmp_path) == original


def test_save_store_leaves_no_temp_file_after_success(tmp_path):
    world_model.save_store({"version": 1, "world_id": WORLD_A, "sectors": {}}, WORLD_A, state_dir=tmp_path)
    path = tmp_path / WORLD_A / "sectors.json"
    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert path.exists()


def test_save_store_creates_file_with_0600_permissions(tmp_path):
    world_model.save_store({"version": 1, "world_id": WORLD_A, "sectors": {}}, WORLD_A, state_dir=tmp_path)
    path = tmp_path / WORLD_A / "sectors.json"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_save_store_atomic_write_survives_a_crash_before_rename(tmp_path, monkeypatch):
    original = {"version": 1, "world_id": WORLD_A, "sectors": {"1": world_model._default_sector(1)}}
    world_model.save_store(original, WORLD_A, state_dir=tmp_path)

    def boom(*_a, **_kw):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(world_model.os, "replace", boom)

    with pytest.raises(OSError):
        world_model.save_store(
            {"version": 1, "world_id": WORLD_A, "sectors": {"2": world_model._default_sector(2)}},
            WORLD_A, state_dir=tmp_path,
        )

    assert world_model.load_store(WORLD_A, state_dir=tmp_path) == original


def test_save_store_removes_orphaned_tmp_file_on_write_failure(tmp_path, monkeypatch):
    original = {"version": 1, "world_id": WORLD_A, "sectors": {}}
    world_model.save_store(original, WORLD_A, state_dir=tmp_path)

    def boom(*_a, **_kw):
        raise ValueError("simulated write-time failure")

    monkeypatch.setattr(world_model.json, "dump", boom)

    with pytest.raises(ValueError):
        world_model.save_store(
            {"version": 1, "world_id": WORLD_A, "sectors": {"1": world_model._default_sector(1)}},
            WORLD_A, state_dir=tmp_path,
        )

    path = tmp_path / WORLD_A / "sectors.json"
    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert world_model.load_store(WORLD_A, state_dir=tmp_path) == original


# -- corrupt/malformed store files ------------------------------------------

def test_load_store_raises_on_truncated_json(tmp_path):
    path = tmp_path / WORLD_A / "sectors.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"version": 1, "sectors": {', encoding="utf-8")
    with pytest.raises(world_model.WorldModelError):
        world_model.load_store(WORLD_A, state_dir=tmp_path)


def test_load_store_raises_on_empty_file(tmp_path):
    path = tmp_path / WORLD_A / "sectors.json"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    with pytest.raises(world_model.WorldModelError):
        world_model.load_store(WORLD_A, state_dir=tmp_path)


def test_load_store_raises_on_unsupported_version(tmp_path):
    path = tmp_path / WORLD_A / "sectors.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 999, "sectors": {}}), encoding="utf-8")
    with pytest.raises(world_model.WorldModelError, match="999"):
        world_model.load_store(WORLD_A, state_dir=tmp_path)


def test_load_store_raises_on_sector_entry_missing_sector_id(tmp_path):
    path = tmp_path / WORLD_A / "sectors.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"version": 1, "sectors": {"1": {"warps": []}}}), encoding="utf-8"
    )
    with pytest.raises(world_model.WorldModelError):
        world_model.load_store(WORLD_A, state_dir=tmp_path)


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
    first = world_model.upsert_sector(
        WORLD_A, {"sector_id": 1, "last_seen_ts": "2026-07-18T00:00:00Z"}, state_dir=tmp_path
    )
    second = world_model.upsert_sector(
        WORLD_A, {"sector_id": 1, "last_seen_ts": "2026-07-19T00:00:00Z"}, state_dir=tmp_path
    )
    assert first["last_seen_ts"] == "2026-07-18T00:00:00Z"
    assert second["last_seen_ts"] == "2026-07-19T00:00:00Z"


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
    assert not (tmp_path / WORLD_A / "sectors.json").exists()


def test_bulk_upsert_acquires_the_lock_only_once(tmp_path, monkeypatch):
    """One lock hold for the whole batch, not one per record -- proves
    the batch-write path really is a single load-mutate-save critical
    section, not N of them."""
    acquisitions = []
    real_store_lock = world_model._store_lock

    def counting_lock(world_id, state_dir=None):
        acquisitions.append(1)
        return real_store_lock(world_id, state_dir=state_dir)

    monkeypatch.setattr(world_model, "_store_lock", counting_lock)
    records = [{"sector_id": i} for i in range(1, 11)]
    world_model.bulk_upsert(WORLD_A, records, state_dir=tmp_path)
    assert len(acquisitions) == 1


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


def test_two_worlds_persist_to_distinct_files(tmp_path):
    world_model.upsert_sector(WORLD_A, {"sector_id": 1}, state_dir=tmp_path)
    world_model.upsert_sector(WORLD_B, {"sector_id": 1}, state_dir=tmp_path)
    assert (tmp_path / WORLD_A / "sectors.json").exists()
    assert (tmp_path / WORLD_B / "sectors.json").exists()
    assert (tmp_path / WORLD_A / "sectors.json") != (tmp_path / WORLD_B / "sectors.json")


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
    assert merged["port"]["class"] is None  # state_parser doesn't extract class today
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


# -- concurrency: lock closes the lost-update races --------------------------

def test_store_lock_real_flock_blocks_second_acquirer_until_released(tmp_path):
    """Real flock proof -- no monkeypatch, no threads: a second, wholly
    independent open-file-description on the same lock path cannot take
    LOCK_EX while the first holds it, and can immediately after the
    first releases."""
    path = world_model._store_path(WORLD_A, tmp_path)
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


def test_concurrent_upsert_never_loses_an_update(tmp_path, monkeypatch):
    """Adapted from player_bank's Trace-1: without a lock spanning the
    FULL load-mutate-save critical section, two concurrent upserts to
    DIFFERENT sectors in the same world can race so the second
    caller's save (built from a stale, pre-first-caller load) silently
    overwrites the first caller's write -- one sector just vanishes.
    Real threads + a monkeypatch hook pause the first writer mid-
    critical-section (still holding the real flock) so the second
    writer's own lock acquisition is forced to actually block until
    release, proving the fix."""
    real_save_store = world_model.save_store
    first_holding = threading.Event()
    release_first = threading.Event()

    def hook(store, world_id, state_dir=None):
        if "1" in store["sectors"]:
            first_holding.set()
            assert release_first.wait(timeout=5), "test deadlocked waiting for release"
        return real_save_store(store, world_id, state_dir=state_dir)

    monkeypatch.setattr(world_model, "save_store", hook)

    errors = []

    def write(sector_id):
        try:
            world_model.upsert_sector(WORLD_A, {"sector_id": sector_id}, state_dir=tmp_path)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=write, args=(1,))
    t2 = threading.Thread(target=write, args=(2,))

    t1.start()
    assert first_holding.wait(timeout=5), "first writer never reached its critical section"
    t2.start()
    time.sleep(0.2)  # give the second writer a real chance to attempt (and block on) the lock
    release_first.set()

    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not errors, f"unexpected error(s) from concurrent upsert_sector: {errors}"
    sector_ids = {s["sector_id"] for s in world_model.all_sectors(WORLD_A, state_dir=tmp_path)}
    assert sector_ids == {1, 2}, "lost update -- one upsert_sector call was silently discarded"


def test_real_concurrent_upsert_across_many_threads_never_loses_an_update(tmp_path):
    """The acceptance bar (mirrors player_bank's real-writer test): N
    real threads hammering the real public API against ONE shared world
    store at the same instant (a `threading.Barrier` maximizes overlap).
    The lock must guarantee zero lost updates regardless of how the OS
    actually schedules them."""
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
