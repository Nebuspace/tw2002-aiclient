"""Game Knowledge Store tests (TW-25) -- no network, tmp_path only,
never touches the real config/ or state/ directories.

`twclient.world_identity` (LANE-W, a sibling lane building concurrently)
does not exist in this worktree yet -- `game_knowledge.py` imports its
pinned `world_id(host, game_letter, handle) -> str` interface at module
level, so a plain `from twclient import game_knowledge` would otherwise
raise ImportError here. The block below registers a tiny local stub
under `twclient.world_identity` in `sys.modules` -- but ONLY if the real
module truly isn't importable yet (checked via `importlib.util.find_spec`,
which never actually imports it) -- so once LANE-W's real module lands
in a shared worktree, these tests transparently start exercising the
REAL `world_id()` instead, with zero code change here. This module never
creates `twclient/world_identity.py` itself; the stub lives only in
`sys.modules`, never on disk.
"""

import importlib.util
import sys
import threading
import types

import pytest

if importlib.util.find_spec("twclient.world_identity") is None:
    _stub = types.ModuleType("twclient.world_identity")

    def _stub_world_id(host, game_letter, handle):
        """Matches the PINNED signature exactly: world_id(host,
        game_letter, handle) -> filesystem-safe slug. A real
        implementation (LANE-W) presumably does more normalization --
        this stub only needs to be stable and injective enough to prove
        cross-world isolation in these tests."""
        raw = f"{host}_{game_letter}_{handle}".lower()
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)

    _stub.world_id = _stub_world_id
    sys.modules["twclient.world_identity"] = _stub

from twclient import game_knowledge  # noqa: E402 (must follow the stub injection above)


# -- knowledge_path (the one world_id()-consuming call) ------------------------

def test_knowledge_path_uses_world_id_to_build_the_slug_directory(tmp_path):
    path = game_knowledge.knowledge_path("alpha.example", "F", "ALPHAH", state_dir=tmp_path)
    assert path.name == "game_knowledge.json"
    assert path.parent.parent == tmp_path / "world"
    # the slug directory must actually reflect the identity triple, not
    # some constant/ignored value.
    assert "alpha" in path.parent.name


def test_knowledge_path_differs_for_different_identity_triples(tmp_path):
    path_a = game_knowledge.knowledge_path("host1", "F", "HANDLEA", state_dir=tmp_path)
    path_b = game_knowledge.knowledge_path("host1", "F", "HANDLEB", state_dir=tmp_path)
    assert path_a != path_b


# -- load_knowledge / save_knowledge -------------------------------------------

def test_load_knowledge_missing_file_returns_fresh_empty_structure(tmp_path):
    path = tmp_path / "game_knowledge.json"
    data = game_knowledge.load_knowledge(path)
    assert data["version"] == game_knowledge.SCHEMA_VERSION
    assert data["menu_map"] == {"nodes": {}, "edges": []}
    assert data["game_data"] == {t: {} for t in game_knowledge.GAME_DATA_TABLES}
    assert not path.exists()  # load never creates the file


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "game_knowledge.json"
    original = game_knowledge._new_knowledge()
    game_knowledge.save_knowledge(original, path)
    assert game_knowledge.load_knowledge(path) == original


def test_save_knowledge_creates_file_with_0600_permissions(tmp_path):
    import os
    import stat

    path = tmp_path / "game_knowledge.json"
    game_knowledge.save_knowledge(game_knowledge._new_knowledge(), path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_save_knowledge_leaves_no_temp_file_after_success(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.save_knowledge(game_knowledge._new_knowledge(), path)
    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()


def test_save_knowledge_atomic_write_survives_a_crash_before_rename(tmp_path, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    original = game_knowledge._new_knowledge()
    game_knowledge.save_knowledge(original, path)

    def boom(*_a, **_kw):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(game_knowledge.os, "replace", boom)

    corrupted_attempt = game_knowledge._new_knowledge()
    corrupted_attempt["menu_map"]["nodes"]["x"] = {"signature": "x"}
    with pytest.raises(OSError):
        game_knowledge.save_knowledge(corrupted_attempt, path)

    assert game_knowledge.load_knowledge(path) == original


def test_save_knowledge_removes_orphaned_tmp_file_on_write_failure(tmp_path, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    original = game_knowledge._new_knowledge()
    game_knowledge.save_knowledge(original, path)

    def boom(*_a, **_kw):
        raise ValueError("simulated write-time failure")

    monkeypatch.setattr(game_knowledge.json, "dump", boom)

    with pytest.raises(ValueError):
        game_knowledge.save_knowledge(game_knowledge._new_knowledge(), path)

    tmp_sibling = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert game_knowledge.load_knowledge(path) == original


def test_load_knowledge_raises_on_truncated_json(tmp_path):
    path = tmp_path / "game_knowledge.json"
    path.write_text('{"version": 1, "menu_map": {', encoding="utf-8")
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.load_knowledge(path)


def test_load_knowledge_raises_on_empty_file(tmp_path):
    path = tmp_path / "game_knowledge.json"
    path.write_text("", encoding="utf-8")
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.load_knowledge(path)


def test_load_knowledge_raises_on_unsupported_version(tmp_path):
    import json

    path = tmp_path / "game_knowledge.json"
    path.write_text(json.dumps({"version": 999}), encoding="utf-8")
    with pytest.raises(game_knowledge.GameKnowledgeError, match="999"):
        game_knowledge.load_knowledge(path)


def test_load_knowledge_never_silently_resets_a_corrupt_file_to_empty(tmp_path):
    path = tmp_path / "game_knowledge.json"
    path.write_text("not json at all {{{", encoding="utf-8")
    try:
        game_knowledge.load_knowledge(path)
    except game_knowledge.GameKnowledgeError:
        pass
    else:
        pytest.fail("expected GameKnowledgeError, got a silent empty store instead")


# -- menu-map: node upsert ------------------------------------------------------

def test_upsert_menu_node_creates_new_node_with_first_and_last_seen(tmp_path):
    path = tmp_path / "game_knowledge.json"
    node = game_knowledge.upsert_menu_node(path, "sig-main-menu", label="Main Command Menu")
    assert node["signature"] == "sig-main-menu"
    assert node["label"] == "Main Command Menu"
    assert node["first_seen_ts"] == node["last_seen_ts"]


def test_upsert_menu_node_is_idempotent_and_updates_last_seen_not_first_seen(tmp_path):
    path = tmp_path / "game_knowledge.json"
    first = game_knowledge.upsert_menu_node(path, "sig-main-menu")

    # force a distinguishable timestamp on the second upsert
    import time

    time.sleep(0.01)
    second = game_knowledge.upsert_menu_node(path, "sig-main-menu", label="Main Menu")

    assert second["first_seen_ts"] == first["first_seen_ts"]
    assert second["label"] == "Main Menu"
    assert len(game_knowledge.list_menu_nodes(path)) == 1  # never duplicated


def test_upsert_menu_node_without_label_preserves_prior_label(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_node(path, "sig-main-menu", label="Main Menu")
    updated = game_knowledge.upsert_menu_node(path, "sig-main-menu")  # label=None
    assert updated["label"] == "Main Menu"


def test_upsert_menu_node_refuses_empty_signature(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_menu_node(path, "")
    assert not path.exists()


def test_get_menu_node_returns_none_when_unseen(tmp_path):
    path = tmp_path / "game_knowledge.json"
    assert game_knowledge.get_menu_node(path, "nope") is None


def test_get_menu_node_returns_a_copy_not_a_live_reference(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_node(path, "sig-a")
    node = game_knowledge.get_menu_node(path, "sig-a")
    node["label"] = "mutated"
    assert game_knowledge.get_menu_node(path, "sig-a")["label"] is None


# -- menu-map: edge upsert -------------------------------------------------------

def test_upsert_menu_edge_creates_new_edge(tmp_path):
    path = tmp_path / "game_knowledge.json"
    edge = game_knowledge.upsert_menu_edge(
        path, "sig-main-menu", "T", "sig-trade-menu", kind="nav", desc="Trade submenu"
    )
    assert edge == {
        "from_node": "sig-main-menu",
        "key": "T",
        "to_node": "sig-trade-menu",
        "kind": "nav",
        "desc": "Trade submenu",
        "last_seen_ts": edge["last_seen_ts"],
    }
    assert len(game_knowledge.list_menu_edges(path)) == 1


def test_upsert_menu_edge_same_from_node_and_key_updates_in_place(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-b", kind="nav")
    game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-c", kind="action", desc="changed")

    edges = game_knowledge.list_menu_edges(path)
    assert len(edges) == 1  # updated in place, not appended
    assert edges[0]["to_node"] == "sig-c"
    assert edges[0]["kind"] == "action"
    assert edges[0]["desc"] == "changed"


def test_upsert_menu_edge_refuses_invalid_kind(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-b", kind="bogus")
    assert not path.exists()


@pytest.mark.parametrize("missing_field", ["from_node", "key", "to_node"])
def test_upsert_menu_edge_refuses_empty_required_fields(tmp_path, missing_field):
    path = tmp_path / "game_knowledge.json"
    args = {"from_node": "sig-a", "key": "X", "to_node": "sig-b"}
    args[missing_field] = ""
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_menu_edge(
            path, args["from_node"], args["key"], args["to_node"]
        )


def test_get_edges_from_returns_only_matching_adjacency(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-b")
    game_knowledge.upsert_menu_edge(path, "sig-a", "Y", "sig-c")
    game_knowledge.upsert_menu_edge(path, "sig-b", "Z", "sig-d")

    from_a = game_knowledge.get_edges_from(path, "sig-a")
    assert {e["key"] for e in from_a} == {"X", "Y"}
    assert all(e["from_node"] == "sig-a" for e in from_a)


# -- menu-map: path lookup (BFS) -------------------------------------------------

def test_find_menu_path_trivial_same_node(tmp_path):
    path = tmp_path / "game_knowledge.json"
    assert game_knowledge.find_menu_path(path, "sig-a", "sig-a") == []


def test_find_menu_path_direct_edge(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-b")
    result = game_knowledge.find_menu_path(path, "sig-a", "sig-b")
    assert [e["key"] for e in result] == ["X"]


def test_find_menu_path_multi_hop_shortest_path(tmp_path):
    path = tmp_path / "game_knowledge.json"
    # a longer direct-ish route and a shorter one through a different node
    game_knowledge.upsert_menu_edge(path, "sig-a", "1", "sig-mid1")
    game_knowledge.upsert_menu_edge(path, "sig-mid1", "2", "sig-mid2")
    game_knowledge.upsert_menu_edge(path, "sig-mid2", "3", "sig-z")
    game_knowledge.upsert_menu_edge(path, "sig-a", "9", "sig-shortcut")
    game_knowledge.upsert_menu_edge(path, "sig-shortcut", "8", "sig-z")

    result = game_knowledge.find_menu_path(path, "sig-a", "sig-z")
    assert [e["key"] for e in result] == ["9", "8"]  # the 2-hop route, not the 3-hop one


def test_find_menu_path_returns_none_when_unreachable(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-b")
    assert game_knowledge.find_menu_path(path, "sig-a", "sig-nowhere") is None


def test_find_menu_path_ignores_cycles(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_edge(path, "sig-a", "X", "sig-b")
    game_knowledge.upsert_menu_edge(path, "sig-b", "Y", "sig-a")  # cycle back
    game_knowledge.upsert_menu_edge(path, "sig-b", "Z", "sig-c")

    result = game_knowledge.find_menu_path(path, "sig-a", "sig-c")
    assert [e["key"] for e in result] == ["X", "Z"]


# -- game-data tables: upsert + read ---------------------------------------------

@pytest.mark.parametrize("table", list(game_knowledge.GAME_DATA_TABLES))
def test_upsert_game_data_row_stamps_source_and_last_verified_ts(tmp_path, table):
    path = tmp_path / "game_knowledge.json"
    row = game_knowledge.upsert_game_data_row(
        path, table, "Widget", {"cost_credits": 5000}, source="introspected: test"
    )
    assert row["key"] == "Widget"
    assert row["source"] == "introspected: test"
    assert "last_verified_ts" in row
    assert row["cost_credits"] == 5000


def test_upsert_game_data_row_preserves_list_valued_fields(tmp_path):
    """special_abilities is explicitly a list-of-string field per
    tw2002-ships-and-equipment.md's Ships table -- must round-trip, not
    be rejected the way player_bank's unrelated secrets-guard rejects
    nested list/dict values."""
    path = tmp_path / "game_knowledge.json"
    row = game_knowledge.upsert_game_data_row(
        path,
        "ships",
        "Merchant Cruiser",
        {
            "max_holds": 75,
            "transwarp_capable": True,
            "special_abilities": ["cloak", "long-range-scan"],
            "alignment_requirement": None,
        },
        source="introspected: shipyard listing",
    )
    assert row["special_abilities"] == ["cloak", "long-range-scan"]
    assert row["alignment_requirement"] is None
    assert row["transwarp_capable"] is True

    reread = game_knowledge.get_game_data_row(path, "ships", "Merchant Cruiser")
    assert reread["special_abilities"] == ["cloak", "long-range-scan"]


def test_upsert_game_data_row_same_key_updates_in_place(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_game_data_row(
        path, "scanners", "density", {"cost_credits": 1000}, source="a"
    )
    game_knowledge.upsert_game_data_row(
        path, "scanners", "density", {"cost_credits": 1200}, source="b"
    )
    rows = game_knowledge.list_game_data_rows(path, "scanners")
    assert len(rows) == 1
    assert rows[0]["cost_credits"] == 1200
    assert rows[0]["source"] == "b"


def test_upsert_game_data_row_refuses_unknown_table(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_game_data_row(path, "bogus_table", "x", {}, source="a")
    assert not path.exists()


def test_upsert_game_data_row_refuses_empty_key(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_game_data_row(path, "ships", "", {}, source="a")


def test_upsert_game_data_row_refuses_empty_source(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_game_data_row(path, "ships", "x", {}, source="")


def test_upsert_game_data_row_refuses_non_dict_fields(tmp_path):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_game_data_row(path, "ships", "x", ["not", "a", "dict"], source="a")


def test_get_game_data_row_returns_none_when_unseen(tmp_path):
    path = tmp_path / "game_knowledge.json"
    assert game_knowledge.get_game_data_row(path, "items", "nope") is None


def test_get_game_data_row_returns_a_copy_not_a_live_reference(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_game_data_row(path, "items", "Genesis Torpedo", {"cost_credits": 1}, source="a")
    row = game_knowledge.get_game_data_row(path, "items", "Genesis Torpedo")
    row["cost_credits"] = 999999
    assert game_knowledge.get_game_data_row(path, "items", "Genesis Torpedo")["cost_credits"] == 1


def test_list_game_data_rows_scoped_to_its_own_table(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_game_data_row(path, "ships", "Cruiser", {}, source="a")
    game_knowledge.upsert_game_data_row(path, "scanners", "density", {}, source="a")

    assert [r["key"] for r in game_knowledge.list_game_data_rows(path, "ships")] == ["Cruiser"]
    assert [r["key"] for r in game_knowledge.list_game_data_rows(path, "scanners")] == ["density"]
    assert game_knowledge.list_game_data_rows(path, "transwarp") == []
    assert game_knowledge.list_game_data_rows(path, "items") == []


# -- cross-world isolation (load-bearing) ----------------------------------------

def test_cross_world_isolation_menu_map_never_bleeds_between_worlds(tmp_path):
    """Two different characters on the same host+game are two
    different worlds (per world_identity's contract) -- their menu-maps
    must never bleed into each other."""
    path_a = game_knowledge.knowledge_path("shared.host", "F", "CHARACTERA", state_dir=tmp_path)
    path_b = game_knowledge.knowledge_path("shared.host", "F", "CHARACTERB", state_dir=tmp_path)
    assert path_a != path_b

    game_knowledge.upsert_menu_node(path_a, "sig-only-in-a")
    game_knowledge.upsert_menu_edge(path_a, "sig-only-in-a", "X", "sig-b-in-a")

    assert game_knowledge.list_menu_nodes(path_b) == []
    assert game_knowledge.list_menu_edges(path_b) == []
    assert len(game_knowledge.list_menu_nodes(path_a)) == 1


def test_cross_world_isolation_game_data_never_bleeds_between_worlds(tmp_path):
    path_a = game_knowledge.knowledge_path("shared.host", "F", "CHARACTERA", state_dir=tmp_path)
    path_b = game_knowledge.knowledge_path("shared.host", "F", "CHARACTERB", state_dir=tmp_path)

    game_knowledge.upsert_game_data_row(
        path_a, "ships", "Only In A", {"max_holds": 10}, source="a"
    )

    assert game_knowledge.list_game_data_rows(path_b, "ships") == []
    assert game_knowledge.get_game_data_row(path_b, "ships", "Only In A") is None
    assert game_knowledge.get_game_data_row(path_a, "ships", "Only In A") is not None


def test_cross_world_isolation_same_host_and_game_different_handle_is_a_different_world(tmp_path):
    """The precise collision this store must avoid: host+game_letter
    alone is NOT enough of a key -- same host, same game letter,
    different handle must resolve to different files."""
    path_1 = game_knowledge.knowledge_path("twgs.example", "A", "PLAYERONE", state_dir=tmp_path)
    path_2 = game_knowledge.knowledge_path("twgs.example", "A", "PLAYERTWO", state_dir=tmp_path)
    assert path_1 != path_2
    assert path_1.parent != path_2.parent


# -- concurrency: lock closes the lost-update races (mirrors player_bank) -------

def test_knowledge_lock_real_flock_blocks_second_acquirer_until_released(tmp_path):
    import fcntl
    import os

    path = tmp_path / "game_knowledge.json"
    lock_path = game_knowledge._lock_path(path)
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


def test_real_concurrent_menu_node_upsert_across_many_threads_never_loses_an_update(tmp_path):
    """Acceptance bar (mirrors player_bank.py's real-concurrency test):
    N real threads, no monkeypatch synchronization, each upserting a
    DIFFERENT node into the SAME knowledge file at (as close to) the
    same instant via a threading.Barrier. Zero lost updates regardless
    of OS scheduling."""
    n = 16
    path = tmp_path / "game_knowledge.json"
    signatures = [f"sig-{i}" for i in range(n)]

    errors = []
    barrier = threading.Barrier(n)

    def worker(sig):
        try:
            barrier.wait(timeout=5)
            game_knowledge.upsert_menu_node(path, sig, label=f"label-{sig}")
        except Exception as e:  # noqa: BLE001
            errors.append((sig, e))

    threads = [threading.Thread(target=worker, args=(sig,)) for sig in signatures]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected error(s) from real concurrent upsert_menu_node: {errors}"
    final_sigs = {n["signature"] for n in game_knowledge.list_menu_nodes(path)}
    assert final_sigs == set(signatures), (
        f"lost update(s) under real concurrency -- expected {n} nodes, "
        f"got {len(final_sigs)}: missing {set(signatures) - final_sigs}"
    )


def test_real_concurrent_game_data_row_upsert_across_many_threads_never_loses_an_update(tmp_path):
    n = 16
    path = tmp_path / "game_knowledge.json"
    keys = [f"ship-{i}" for i in range(n)]

    errors = []
    barrier = threading.Barrier(n)

    def worker(key):
        try:
            barrier.wait(timeout=5)
            game_knowledge.upsert_game_data_row(
                path, "ships", key, {"max_holds": 10}, source="test"
            )
        except Exception as e:  # noqa: BLE001
            errors.append((key, e))

    threads = [threading.Thread(target=worker, args=(key,)) for key in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected error(s) from real concurrent upsert_game_data_row: {errors}"
    final_keys = {r["key"] for r in game_knowledge.list_game_data_rows(path, "ships")}
    assert final_keys == set(keys), (
        f"lost update(s) under real concurrency -- expected {n} rows, "
        f"got {len(final_keys)}: missing {set(keys) - final_keys}"
    )
