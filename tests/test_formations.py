"""TW-16 formation detector tests."""

from pathlib import Path

from twclient import world_model
from twclient.formations import (
    BUBBLE,
    DEAD_END,
    ONE_WAY,
    WARP_SINK,
    catalog_world,
    detect_formations,
    membership_map,
    write_membership,
)


def test_dead_end():
    graph = {1: (2,), 2: (1, 3), 3: (2,)}
    cat = detect_formations(graph)
    dead = cat.by_kind(DEAD_END)
    assert {f.sectors[0] for f in dead} == {1, 3}
    assert all(f in cat.genesis_candidates for f in dead)


def test_bubble_single_entrance():
    # Pocket {10,11,12} entered only via 10↔2; outside 1—2
    graph = {
        1: (2,),
        2: (1, 10),
        10: (2, 11, 12),
        11: (10, 12),
        12: (10, 11),
    }
    cat = detect_formations(graph)
    bubbles = cat.by_kind(BUBBLE)
    assert len(bubbles) == 1
    assert set(bubbles[0].sectors) == {10, 11, 12}
    assert bubbles[0].entrance == 10
    assert bubbles[0] in cat.genesis_candidates


def test_one_way_warp():
    graph = {1: (2,), 2: (3,), 3: (2,)}  # 1→2 no reverse
    cat = detect_formations(graph)
    ones = cat.by_kind(ONE_WAY)
    assert any(f.sectors == (1, 2) for f in ones)
    assert all(f not in cat.genesis_candidates for f in ones)


def test_warp_sink_no_exit():
    # 1→2→3, 3 has no out; 2←3 mutual so 3 not dead-end of outdeg1...
    # Sink: 4 reachable from 1 via one-way, 4 has no outs
    graph = {
        1: (2, 4),
        2: (1,),
        4: (),  # trap
    }
    cat = detect_formations(graph)
    sinks = cat.by_kind(WARP_SINK)
    assert any(4 in f.sectors for f in sinks)
    assert all(f not in cat.genesis_candidates for f in sinks)


def test_catalog_world_and_write_membership(tmp_path: Path):
    wid = "test+form"
    world_model.bulk_upsert(
        wid,
        [
            {"sector_id": 5, "warps": [6]},
            {"sector_id": 6, "warps": [5, 7]},
            {"sector_id": 7, "warps": [6]},
        ],
        state_dir=tmp_path,
    )
    cat = catalog_world(wid, state_dir=tmp_path)
    assert cat.known_sectors == 3
    assert any(f.kind == DEAD_END and f.sectors == (5,) for f in cat.formations)
    n = write_membership(wid, cat, state_dir=tmp_path)
    assert n >= 1
    rec = world_model.get_sector(wid, 5, state_dir=tmp_path)
    assert DEAD_END in (rec.get("formation_membership") or [])


def test_membership_map_dedupes_kinds():
    cat = detect_formations({1: (2,), 2: (1,)})
    m = membership_map(cat)
    for tags in m.values():
        assert len(tags) == len(set(tags))
