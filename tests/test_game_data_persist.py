"""TW-26/27 write lane -- persist/query path tests for `game_data.py`'s
bridge over `game_knowledge.py`'s per-world "ships" game-data table.

No network, `tmp_path`-only (`state_dir=` threaded through every call
below), never touches the real gitignored `state/` tree -- mirrors
`tests/test_world_model.py` / `tests/test_player_bank.py` /
`tests/test_game_knowledge.py`'s isolation discipline.
"""

import threading

import pytest

from twclient import game_data, game_knowledge

WORLD_A = "hostA__F__ALPHA"
WORLD_B = "hostB__F__BRAVO"


def _ship_row(**overrides):
    """A minimally-valid, INTROSPECTED ship row dict conforming to
    `game_data.ShipRow` -- the PINNED input shape TW-27's introspector
    produces. `overrides` lets a test tweak one or two fields without
    repeating the whole shape."""
    row = {
        "ship_name": "Fixture Scout",
        "max_holds": 10,
        "max_fighters": 5,
        "max_shields": 2,
        "combat_odds_modifier": 1.0,
        "turns_per_warp": 3,
        "base_cost_credits": 1000,
        "alignment_requirement": None,
        "rank_requirement": None,
        "transwarp_capable": False,
        "special_abilities": [],
        "source": "introspected: shipyard listing (test)",
        "last_verified_ts": "2026-07-19T00:00:00Z",
    }
    row.update(overrides)
    return row


# -- persist + read-back round trip ------------------------------------------

def test_persist_ship_row_then_get_ship_round_trips(tmp_path):
    persisted = game_data.persist_ship_row(WORLD_A, _ship_row(), state_dir=tmp_path)
    assert isinstance(persisted, game_data.ShipRow)
    assert persisted.ship_name == "Fixture Scout"
    assert persisted.max_holds == 10

    fetched = game_data.get_ship(WORLD_A, "Fixture Scout", state_dir=tmp_path)
    assert fetched == persisted


def test_persist_ship_row_preserves_list_and_none_valued_fields(tmp_path):
    game_data.persist_ship_row(
        WORLD_A,
        _ship_row(
            ship_name="Merchant Cruiser",
            special_abilities=["cloak", "long-range-scan"],
            alignment_requirement=None,
            rank_requirement=None,
            transwarp_capable=True,
        ),
        state_dir=tmp_path,
    )
    fetched = game_data.get_ship(WORLD_A, "Merchant Cruiser", state_dir=tmp_path)
    assert fetched.special_abilities == ("cloak", "long-range-scan")
    assert fetched.alignment_requirement is None
    assert fetched.rank_requirement is None
    assert fetched.transwarp_capable is True


def test_persist_ship_row_writes_into_the_existing_game_knowledge_store(tmp_path):
    """Not a second/parallel store -- the row must land inside the SAME
    per-world game_knowledge.json the menu-map graph already lives in."""
    game_data.persist_ship_row(WORLD_A, _ship_row(), state_dir=tmp_path)
    path = game_knowledge.knowledge_path_for_world(WORLD_A, state_dir=tmp_path)
    assert path.exists()
    assert path.name == "game_knowledge.json"
    rows = game_knowledge.list_game_data_rows(path, "ships")
    assert [r["key"] for r in rows] == ["Fixture Scout"]


# -- introspector write-time timestamp seam (Lane B contract) ---------------
#
# TW-27's introspector is a pure parser with no clock and deliberately
# OMITS `last_verified_ts` from every row it emits -- its own docstring
# names `persist_ship_row` as the caller responsible for stamping it at
# write time. This worktree doesn't have `introspector.py` (Lane B's
# separate worktree) -- the row below is built inline to mirror its
# EXACT documented output shape (every required ship field present
# EXCEPT `last_verified_ts` -- no ts key at all), so this test locks
# the seam without a cross-worktree import.

def test_persist_ship_row_stamps_last_verified_ts_for_a_tsless_introspector_row(tmp_path):
    introspector_row = {
        "ship_name": "Merchant Cruiser",
        "max_holds": 75,
        "max_fighters": 20,
        "max_shields": 20,
        "combat_odds_modifier": 1.0,
        "turns_per_warp": 2,
        "base_cost_credits": 68000,
        "alignment_requirement": None,
        "rank_requirement": None,
        "transwarp_capable": False,
        "special_abilities": [],
        "source": "introspected: stardock_shipyard",
        # NOTE: no "last_verified_ts" key at all -- the introspector's
        # documented contract.
    }
    assert "last_verified_ts" not in introspector_row  # sanity: shape matches the contract

    persisted = game_data.persist_ship_row(WORLD_A, introspector_row, state_dir=tmp_path)
    assert isinstance(persisted.last_verified_ts, str) and persisted.last_verified_ts

    fetched = game_data.get_ship(WORLD_A, "Merchant Cruiser", state_dir=tmp_path)
    assert fetched is not None
    assert isinstance(fetched.last_verified_ts, str) and fetched.last_verified_ts
    assert fetched.max_holds == 75


def test_get_ship_returns_none_when_unseen(tmp_path):
    assert game_data.get_ship(WORLD_A, "Never Persisted", state_dir=tmp_path) is None


def test_list_ships_empty_for_a_world_with_no_persisted_ships(tmp_path):
    assert game_data.list_ships(WORLD_A, state_dir=tmp_path) == ()


def test_list_ships_returns_every_persisted_ship(tmp_path):
    game_data.persist_ship_row(WORLD_A, _ship_row(ship_name="Scout"), state_dir=tmp_path)
    game_data.persist_ship_row(WORLD_A, _ship_row(ship_name="Cruiser"), state_dir=tmp_path)
    names = {s.ship_name for s in game_data.list_ships(WORLD_A, state_dir=tmp_path)}
    assert names == {"Scout", "Cruiser"}


# -- introspected-only enforcement AT PERSIST (not just at load) ------------

def test_persist_ship_row_rejects_non_introspected_source(tmp_path):
    with pytest.raises(ValueError, match="introspected"):
        game_data.persist_ship_row(
            WORLD_A,
            _ship_row(source="authored: wiki"),
            state_dir=tmp_path,
        )
    # rejected before the store is ever touched -- no file, no partial write.
    path = game_knowledge.knowledge_path_for_world(WORLD_A, state_dir=tmp_path)
    assert not path.exists()


def test_persist_ship_row_rejects_missing_required_field(tmp_path):
    row = _ship_row()
    del row["max_holds"]
    with pytest.raises(ValueError, match="max_holds"):
        game_data.persist_ship_row(WORLD_A, row, state_dir=tmp_path)
    path = game_knowledge.knowledge_path_for_world(WORLD_A, state_dir=tmp_path)
    assert not path.exists()


def test_persist_ship_row_rejection_does_not_clobber_an_existing_good_row(tmp_path):
    """A later rejected write for the SAME ship must not touch the
    already-persisted good row -- validation runs before any lock/write."""
    game_data.persist_ship_row(WORLD_A, _ship_row(max_holds=10), state_dir=tmp_path)
    with pytest.raises(ValueError):
        game_data.persist_ship_row(
            WORLD_A, _ship_row(max_holds=999, source="authored: bad"), state_dir=tmp_path
        )
    assert game_data.get_ship(WORLD_A, "Fixture Scout", state_dir=tmp_path).max_holds == 10


# -- last-introspection-wins supersede ---------------------------------------

def test_persist_ship_row_newer_capture_supersedes_older_row(tmp_path, monkeypatch):
    # `game_knowledge._now_iso()` has SECOND resolution -- two persists
    # in the same test can otherwise land the same stamp and make this
    # assertion flaky (mirrors test_game_knowledge.py's own
    # idempotent-upsert test forcing a distinguishable timestamp, but
    # via monkeypatch here rather than a real sleep).
    stamps = iter(["2026-07-19T00:00:01Z", "2026-07-19T00:00:02Z"])
    monkeypatch.setattr(game_knowledge, "_now_iso", lambda: next(stamps))

    first = game_data.persist_ship_row(
        WORLD_A,
        _ship_row(max_holds=10, last_verified_ts="2026-07-01T00:00:00Z"),
        state_dir=tmp_path,
    )
    second = game_data.persist_ship_row(
        WORLD_A,
        _ship_row(max_holds=15, last_verified_ts="2026-07-19T00:00:00Z"),
        state_dir=tmp_path,
    )
    ships = game_data.list_ships(WORLD_A, state_dir=tmp_path)
    assert len(ships) == 1  # updated in place, never duplicated
    assert ships[0].max_holds == 15
    # `last_verified_ts` is timestamp-stamped at PERSIST time (mirrors
    # `game_knowledge.py`'s existing always-fresh-stamp-on-upsert
    # discipline -- the same "last_seen_ts always advances" rule
    # world_model.py's per-sector store follows) -- never trusted
    # verbatim from the caller's own row, so the second persist's stamp
    # must differ from (be fresher than) the first's.
    assert second.last_verified_ts != first.last_verified_ts
    assert ships[0].last_verified_ts == second.last_verified_ts


# -- cross-world isolation (load-bearing) ------------------------------------

def test_cross_world_isolation_ships_never_bleed_between_worlds(tmp_path):
    game_data.persist_ship_row(WORLD_A, _ship_row(ship_name="Only In A"), state_dir=tmp_path)

    assert game_data.list_ships(WORLD_B, state_dir=tmp_path) == ()
    assert game_data.get_ship(WORLD_B, "Only In A", state_dir=tmp_path) is None
    assert game_data.get_ship(WORLD_A, "Only In A", state_dir=tmp_path) is not None


def test_cross_world_isolation_same_ship_name_different_values_per_world(tmp_path):
    """Two worlds may each introspect a ship of the same name with
    DIFFERENT server-specific numbers -- neither may overwrite the
    other's row."""
    game_data.persist_ship_row(WORLD_A, _ship_row(max_holds=10), state_dir=tmp_path)
    game_data.persist_ship_row(WORLD_B, _ship_row(max_holds=999), state_dir=tmp_path)

    assert game_data.get_ship(WORLD_A, "Fixture Scout", state_dir=tmp_path).max_holds == 10
    assert game_data.get_ship(WORLD_B, "Fixture Scout", state_dir=tmp_path).max_holds == 999


# -- filter-by-alignment-flyable ----------------------------------------------

def test_list_flyable_ships_ungated_ship_always_passes(tmp_path):
    game_data.persist_ship_row(
        WORLD_A, _ship_row(ship_name="Basic Freighter", alignment_requirement=None), state_dir=tmp_path
    )
    flyable = game_data.list_flyable_ships(WORLD_A, alignment=None, state_dir=tmp_path)
    assert {s.ship_name for s in flyable} == {"Basic Freighter"}


def test_list_flyable_ships_gated_ship_requires_sufficient_alignment(tmp_path):
    game_data.persist_ship_row(
        WORLD_A,
        _ship_row(ship_name="Imperial Starship", alignment_requirement=600),
        state_dir=tmp_path,
    )
    assert game_data.list_flyable_ships(WORLD_A, alignment=599, state_dir=tmp_path) == ()
    flyable = game_data.list_flyable_ships(WORLD_A, alignment=600, state_dir=tmp_path)
    assert {s.ship_name for s in flyable} == {"Imperial Starship"}


def test_list_flyable_ships_unknown_alignment_only_passes_ungated_ships(tmp_path):
    game_data.persist_ship_row(
        WORLD_A, _ship_row(ship_name="Ungated", alignment_requirement=None), state_dir=tmp_path
    )
    game_data.persist_ship_row(
        WORLD_A, _ship_row(ship_name="Gated", alignment_requirement=1), state_dir=tmp_path
    )
    flyable = game_data.list_flyable_ships(WORLD_A, state_dir=tmp_path)  # alignment=None
    assert {s.ship_name for s in flyable} == {"Ungated"}


# -- concurrent-writer safety (adapts player_bank.py's real-concurrency bar) -

def test_real_concurrent_persist_ship_row_across_many_threads_never_loses_an_update(tmp_path):
    """N real threads, no monkeypatch synchronization, each persisting a
    DIFFERENT ship into the SAME world's store at (as close to) the
    same instant via a threading.Barrier. Zero lost updates regardless
    of OS scheduling -- the flock'd critical section
    `game_knowledge.upsert_game_data_row` already holds is exercised
    through this module's persist path."""
    n = 16
    names = [f"Ship-{i}" for i in range(n)]

    errors = []
    barrier = threading.Barrier(n)

    def worker(name):
        try:
            barrier.wait(timeout=5)
            game_data.persist_ship_row(WORLD_A, _ship_row(ship_name=name), state_dir=tmp_path)
        except Exception as e:  # noqa: BLE001
            errors.append((name, e))

    threads = [threading.Thread(target=worker, args=(name,)) for name in names]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected error(s) from real concurrent persist_ship_row: {errors}"
    final_names = {s.ship_name for s in game_data.list_ships(WORLD_A, state_dir=tmp_path)}
    assert final_names == set(names), (
        f"lost update(s) under real concurrency -- expected {n} ships, "
        f"got {len(final_names)}: missing {set(names) - final_names}"
    )
