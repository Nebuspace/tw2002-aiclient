"""WO-GOALS-STATUS-VOCABULARY T1 — `world_stats.WorldStats` + the count it reads.

`tests/test_play_chains_discovered.py` pins the WIRE (that `_run_play` calls
`refresh`, against this profile's world, and that the number reaches the closure
GOALS polls). This file pins the BEHAVIOUR the wire delivers, and one property
that is easy to lose without noticing: **`None` is not zero**.

`world_model.known_sector_count` must distinguish "no sector has ever been
written for this world" (genuinely zero, and honest to report) from "the store
cannot be read" (unknown, and reporting zero there would fabricate "you have
explored nothing" out of a permissions error). `Path.glob` — which every
neighbouring reader in `world_model.py` uses — CANNOT make that distinction: it
swallows `PermissionError` and yields nothing, so an unreadable directory and an
empty one are byte-identical through it. That is the whole reason this function
uses `os.scandir`, and the reason the unreadable case below is pinned with a
readable positive control beside it: a function that returned `None`
unconditionally would pass the negative half alone.
"""

from __future__ import annotations

import json
import os
import stat

import pytest

from tw2002_aiclient import chain_status, world_model, world_stats

WORLD = "w-test"


def _store(root, sector_ids):
    d = root / WORLD / "sectors"
    d.mkdir(parents=True)
    for sid in sector_ids:
        (d / f"{sid}.json").write_text(json.dumps({"sector_id": sid, "warps": []}))
    return d


# ------------------------------------------------- known_sector_count


def test_it_counts_the_sector_files(tmp_path):
    _store(tmp_path, [1, 2, 3, 41, 512])
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 5


def test_it_agrees_with_all_sectors(tmp_path):
    """The cheap count and the expensive list must not drift apart — the whole
    argument for the count existing is that it answers the same question."""
    _store(tmp_path, [7, 8, 9, 10])
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == len(
        world_model.all_sectors(WORLD, state_dir=tmp_path)
    )


def test_a_world_never_written_counts_zero(tmp_path):
    """Zero here is a fact, not a fabrication: nothing has ever been stored for
    this world, so nothing is known. `all_sectors` says the same with []."""
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 0
    assert world_model.all_sectors(WORLD, state_dir=tmp_path) == []


def test_lock_siblings_and_stray_files_are_not_counted(tmp_path):
    """`<sector_id>.json.lock` files live beside the records, and a stray
    non-numeric `*.json` would make `all_sectors` raise on `int(stem)` — this
    skips it rather than counting or exploding."""
    d = _store(tmp_path, [1, 2])
    (d / "1.json.lock").write_text("")
    (d / "2.json.lock").write_text("")
    (d / "notes.json").write_text("{}")
    (d / "3.txt").write_text("")
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 2


def test_it_does_not_read_the_files(tmp_path):
    """A count that parsed every record would cost what `all_sectors` costs,
    which is the entire reason this function exists. Unparseable content is the
    cheapest observable proof it never opened them."""
    d = _store(tmp_path, [1, 2, 3])
    (d / "2.json").write_text("}{ not json at all")
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 3
    with pytest.raises(world_model.WorldModelError):
        world_model.all_sectors(WORLD, state_dir=tmp_path)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unreadable_store_is_unknown_not_zero(tmp_path):
    """The load-bearing distinction, with its own positive control.

    Without the control, a function that always returned `None` would pass.
    Without the assertion, `Path.glob`'s silent `PermissionError` swallow would
    report 0 known sectors — telling the operator they have explored nothing
    because a directory mode changed.
    """
    d = _store(tmp_path, [1, 2, 3, 4])
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 4  # control
    d.chmod(0o000)
    try:
        assert world_model.known_sector_count(WORLD, state_dir=tmp_path) is None
    finally:
        d.chmod(stat.S_IRWXU)
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 4  # restored


def test_a_file_where_the_sectors_dir_should_be_is_unknown_not_zero(tmp_path):
    (tmp_path / WORLD).mkdir(parents=True)
    (tmp_path / WORLD / "sectors").write_text("not a directory")
    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) is None


# ------------------------------------------------- WorldStats


class _FakeWM:
    def __init__(self, *results):
        self.results = list(results)
        self.calls: list = []

    def known_sector_count(self, world_id, **kw):
        self.calls.append(world_id)
        r = self.results.pop(0) if self.results else None
        if isinstance(r, BaseException):
            raise r
        return r


@pytest.fixture
def wm(monkeypatch):
    fake = _FakeWM()
    monkeypatch.setattr(world_model, "known_sector_count", fake.known_sector_count)
    return fake


def test_it_contributes_nothing_before_a_refresh(wm):
    s = world_stats.WorldStats()
    assert s.merge({"ok": True}) == {"ok": True}
    assert wm.calls == [], "reading the world model without being asked to"


def test_a_refresh_supplies_the_count(wm):
    wm.results = [812]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {"ok": True, "known_sectors": 812}
    assert wm.calls == ["w-1"]


def test_zero_is_supplied_not_swallowed(wm):
    """A world we HAVE looked at and found empty reports 0. Treating the count
    as falsy-means-absent would turn a measured fact back into "unknown"."""
    wm.results = [0]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({}) == {"known_sectors": 0}


def test_it_never_mutates_the_status_it_is_given(wm):
    wm.results = [5]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    original = {"ok": True}
    s.merge(original)
    assert original == {"ok": True}


def test_a_supplied_value_wins(wm):
    """If a future daemon-side producer starts emitting the field, this cache
    must not overwrite a fresher number with its own older one."""
    wm.results = [5]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"known_sectors": 99}) == {"known_sectors": 99}


def test_a_supplied_none_is_filled_in(wm):
    wm.results = [5]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"known_sectors": None}) == {"known_sectors": 5}


@pytest.mark.parametrize(
    "bad", [None, True, False, -1, "812", 8.5, object()],
    ids=["none", "true", "false", "negative", "str", "float", "junk"],
)
def test_junk_counts_are_refused(wm, bad):
    """`True` is an `int` in Python and would render as "1 sectors"; a negative
    count is not a thing the store can contain. Neither may reach the panel."""
    wm.results = [bad]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {"ok": True}


def test_a_raising_world_model_is_swallowed(wm):
    wm.results = [RuntimeError("store on fire")]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {"ok": True}


def test_a_failed_refresh_keeps_the_last_observed_count(wm):
    """The number was genuinely measured. A later read failing says nothing
    about the moment we measured it, so throwing it away would lose real
    information without gaining any honesty."""
    wm.results = [812, RuntimeError("gone"), None]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    s.refresh("w-1")
    assert s.merge({}) == {"known_sectors": 812}
    s.refresh("w-1")
    assert s.merge({}) == {"known_sectors": 812}


def test_a_non_dict_status_passes_through_untouched(wm):
    wm.results = [5]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    for value in (None, "down", 0, []):
        assert s.merge(value) is value, f"a non-dict status was not passed through: {value!r}"


def test_wrapping_none_stays_none():
    """An absent status source must stay absent, not become a callable that
    returns a stats-only dict — the panel would then think it had a daemon."""
    assert world_stats.WorldStats().wrap(None) is None


def test_wrap_overlays_any_provider(wm):
    wm.results = [812]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.wrap(lambda: {"ok": True})() == {"ok": True, "known_sectors": 812}


def test_the_two_overlays_compose_in_either_order(wm):
    """`app.py` nests `world_stats.wrap(chain_scalars.wrap(provider))`. Each
    overlay adds only its own keys and declines to clobber, so the order must
    not matter — if it ever does, the nesting in `app.py` became load-bearing
    without anyone deciding that it should be."""
    wm.results = [812, 812]
    ws = world_stats.WorldStats()
    ws.refresh("w-1")
    cs = chain_status.ChainScalars()
    cs.update(_discovery(hops=3))

    base = lambda: {"ok": True}  # noqa: E731
    expected = {"ok": True, "known_sectors": 812, "chain_hops": 3, "chain_unit": "hops"}
    assert ws.wrap(cs.wrap(base))() == expected

    ws2 = world_stats.WorldStats()
    ws2.refresh("w-1")
    assert cs.wrap(ws2.wrap(base))() == expected


def _discovery(hops):
    from types import SimpleNamespace

    chain = SimpleNamespace(hops=tuple(object() for _ in range(hops)))
    return SimpleNamespace(chains=(chain,), truncated=False, reason=None)
