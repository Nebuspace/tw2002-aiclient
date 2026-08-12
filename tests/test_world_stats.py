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

from tw2002_aiclient import chain_status, explore, world_model, world_stats

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
        self.landmark_results: list = [[]]
        self.landmark_calls: list = []
        # Separate queue so StarDock tests keep one-result-per-refresh.
        # None → every own_planet lookup returns [] (no planets observed).
        self.own_planet_landmark_results: list | None = None
        # None → every all_sectors call returns [] (completed empty scan).
        self.sector_lists: list | None = None
        self.sector_list_calls: list = []

    def known_sector_count(self, world_id, **kw):
        self.calls.append(world_id)
        r = self.results.pop(0) if self.results else None
        if isinstance(r, BaseException):
            raise r
        return r

    def find_landmark_sectors(self, world_id, landmark_name, **kw):
        self.landmark_calls.append((world_id, landmark_name))
        if str(landmark_name).casefold() == world_model.OWN_PLANET_LANDMARK.casefold():
            if self.own_planet_landmark_results is None:
                return []
            r = (
                self.own_planet_landmark_results.pop(0)
                if self.own_planet_landmark_results
                else []
            )
        else:
            r = self.landmark_results.pop(0) if self.landmark_results else []
        if isinstance(r, BaseException):
            raise r
        return r

    def all_sectors(self, world_id, **kw):
        self.sector_list_calls.append(world_id)
        if self.sector_lists is None:
            return []
        if not self.sector_lists:
            return []
        r = self.sector_lists.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


@pytest.fixture
def wm(monkeypatch):
    fake = _FakeWM()
    monkeypatch.setattr(world_model, "known_sector_count", fake.known_sector_count)
    monkeypatch.setattr(world_model, "all_sectors", fake.all_sectors)
    monkeypatch.setattr(explore, "find_landmark_sectors", fake.find_landmark_sectors)
    return fake


def test_it_contributes_nothing_before_a_refresh(wm):
    s = world_stats.WorldStats()
    assert s.merge({"ok": True}) == {"ok": True}
    assert wm.calls == [], "reading the world model without being asked to"
    assert wm.landmark_calls == [], "scanning landmarks without being asked to"
    assert wm.sector_list_calls == [], "scanning sectors without being asked to"


def test_a_refresh_supplies_the_count(wm):
    wm.results = [812]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {
        "ok": True,
        "known_sectors": 812,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }
    assert wm.calls == ["w-1"]


def test_zero_is_supplied_not_swallowed(wm):
    """A world we HAVE looked at and found empty reports 0. Treating the count
    as falsy-means-absent would turn a measured fact back into "unknown"."""
    wm.results = [0]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({}) == {"known_sectors": 0, "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []}}


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
    assert s.merge({"known_sectors": 99}) == {
        "known_sectors": 99,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


def test_a_supplied_none_is_filled_in(wm):
    wm.results = [5]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"known_sectors": None}) == {
        "known_sectors": 5,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


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
    # known_sectors refused; dead-end scan still completed over [].
    assert s.merge({"ok": True}) == {"ok": True, "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []}}


def test_a_raising_world_model_is_swallowed(wm):
    wm.results = [RuntimeError("store on fire")]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {"ok": True, "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []}}


def test_a_failed_refresh_keeps_the_last_observed_count(wm):
    """The number was genuinely measured. A later read failing says nothing
    about the moment we measured it, so throwing it away would lose real
    information without gaining any honesty."""
    wm.results = [812, RuntimeError("gone"), None]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    s.refresh("w-1")
    assert s.merge({}) == {"known_sectors": 812, "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []}}
    s.refresh("w-1")
    assert s.merge({}) == {"known_sectors": 812, "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []}}


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
    assert s.wrap(lambda: {"ok": True})() == {
        "ok": True,
        "known_sectors": 812,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


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
    expected = {
        "ok": True,
        "known_sectors": 812,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
        "chain_hops": 3,
        "chain_unit": "hops",
    }
    assert ws.wrap(cs.wrap(base))() == expected

    ws2 = world_stats.WorldStats()
    ws2.refresh("w-1")
    assert cs.wrap(ws2.wrap(base))() == expected


def _discovery(hops):
    from types import SimpleNamespace

    chain = SimpleNamespace(hops=tuple(object() for _ in range(hops)))
    return SimpleNamespace(chains=(chain,), truncated=False, reason=None)


# ------------------------------------------------- StarDock landmarks


def test_nonempty_landmarks_supply_sectors_and_found(wm):
    wm.results = [3]
    wm.landmark_results = [[11, 42]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {
        "ok": True,
        "known_sectors": 3,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
        "stardock_sectors": [11, 42],
        "stardock_found": True,
    }
    assert wm.landmark_calls == [
        ("w-1", world_model.STARDOCK_LANDMARK),
        ("w-1", world_model.OWN_PLANET_LANDMARK),
    ]


def test_empty_landmark_scan_omits_stardock_keys(wm):
    """Empty after a successful refresh keeps GOALS at `?` — never confirmed-negative."""
    wm.results = [0]
    wm.landmark_results = [[]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True}) == {
        "ok": True,
        "known_sectors": 0,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }
    assert "stardock_found" not in s.merge({})
    assert "stardock_sectors" not in s.merge({})


def test_empty_scan_never_emits_stardock_found_false(wm):
    wm.results = [1]
    wm.landmark_results = [[]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    merged = s.merge({})
    assert merged.get("stardock_found") is not False
    assert "stardock_found" not in merged


def test_stardock_does_not_clobber_caller_values(wm):
    wm.results = [1]
    wm.landmark_results = [[7]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge(
        {"stardock_sectors": [99], "stardock_found": False}
    ) == {
        "stardock_sectors": [99],
        "stardock_found": False,
        "known_sectors": 1,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


def test_failed_stardock_refresh_keeps_last_observation(wm):
    wm.results = [1, 1, 1]
    wm.landmark_results = [[7], RuntimeError("store on fire"), []]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({})["stardock_sectors"] == [7]
    s.refresh("w-1")  # landmark failure — keep [7]
    assert s.merge({})["stardock_sectors"] == [7]
    assert s.merge({})["stardock_found"] is True
    s.refresh("w-1")  # successful empty — omit keys again
    assert "stardock_sectors" not in s.merge({})
    assert "stardock_found" not in s.merge({})


def test_wrap_reads_only_the_cache(wm):
    """Draw-path wrap must not touch the world model — only the last refresh cache."""
    wm.results = [5]
    wm.landmark_results = [[3]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    calls_after_refresh = list(wm.calls)
    landmark_after_refresh = list(wm.landmark_calls)
    sectors_after_refresh = list(wm.sector_list_calls)
    wrapped = s.wrap(lambda: {"ok": True})
    assert wrapped() == {
        "ok": True,
        "known_sectors": 5,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
        "stardock_sectors": [3],
        "stardock_found": True,
    }
    assert wm.calls == calls_after_refresh
    assert wm.landmark_calls == landmark_after_refresh
    assert wm.sector_list_calls == sectors_after_refresh


def test_junk_landmark_lists_are_refused(wm):
    wm.results = [1]
    wm.landmark_results = [["7"], [True], [1, "x"], "nope"]
    s = world_stats.WorldStats()
    for _ in range(4):
        s.refresh("w-1")
        assert "stardock_sectors" not in s.merge({"ok": True})


# ------------------------------------------------- has_port (WO-COACH-HAS-PORT)


def _hud_status(sector):
    return {"hud": {"sector": {"value": sector, "age_s": 0.0}}}


def test_has_port_omitted_when_refresh_has_no_status(wm):
    wm.results = [0]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert "has_port" not in s.merge({"ok": True})


def test_has_port_true_when_current_sector_has_port(tmp_path, wm):
    wm.results = [1]
    world_model.upsert_sector(
        WORLD,
        {"sector_id": 7, "port": {"last_seen_ts": "t", "class": "BBB"}},
        state_dir=tmp_path,
    )
    s = world_stats.WorldStats()
    s.refresh(WORLD, status=_hud_status(7), state_dir=tmp_path)
    assert s.merge({"ok": True})["has_port"] is True


def test_has_port_omitted_for_unknown_sector(tmp_path, wm):
    wm.results = [0]
    s = world_stats.WorldStats()
    s.refresh(WORLD, status=_hud_status(99), state_dir=tmp_path)
    assert "has_port" not in s.merge({"ok": True})


def test_has_port_omitted_when_sector_port_is_none(tmp_path, wm):
    wm.results = [1]
    world_model.upsert_sector(
        WORLD, {"sector_id": 7, "warps": [1]}, state_dir=tmp_path
    )
    s = world_stats.WorldStats()
    s.refresh(WORLD, status=_hud_status(7), state_dir=tmp_path)
    assert "has_port" not in s.merge({"ok": True})


def test_has_port_clears_when_sector_moves_to_unknown(tmp_path, wm):
    wm.results = [1, 1]
    world_model.upsert_sector(
        WORLD,
        {"sector_id": 7, "port": {"last_seen_ts": "t"}},
        state_dir=tmp_path,
    )
    s = world_stats.WorldStats()
    s.refresh(WORLD, status=_hud_status(7), state_dir=tmp_path)
    assert s.merge({})["has_port"] is True
    s.refresh(WORLD, status=_hud_status(8), state_dir=tmp_path)
    assert "has_port" not in s.merge({"ok": True})


@pytest.mark.parametrize(
    "status",
    [
        {},
        {"hud": None},
        {"hud": "nope"},
        {"hud": {}},
        {"hud": {"sector": None}},
        {"hud": {"sector": "7"}},
        {"hud": {"sector": {"value": None}}},
        {"hud": {"sector": {"value": True}}},
        {"hud": {"sector": {"value": "7"}}},
        {"hud": {"sector": {"value": 7.5}}},
    ],
    ids=[
        "no-hud",
        "hud-none",
        "hud-str",
        "hud-empty",
        "sector-none",
        "sector-str",
        "value-none",
        "value-bool",
        "value-str",
        "value-float",
    ],
)
def test_hostile_hud_sector_never_raises_or_invents_has_port(wm, status):
    wm.results = [0]
    s = world_stats.WorldStats()
    s.refresh("w-1", status=status)
    assert "has_port" not in s.merge({"ok": True})


def test_has_port_does_not_clobber_caller(tmp_path, wm):
    wm.results = [1]
    world_model.upsert_sector(
        WORLD,
        {"sector_id": 7, "port": {"last_seen_ts": "t"}},
        state_dir=tmp_path,
    )
    s = world_stats.WorldStats()
    s.refresh(WORLD, status=_hud_status(7), state_dir=tmp_path)
    assert s.merge({"has_port": False}) == {
        "has_port": False,
        "known_sectors": 1,
        "dead_end_count": 0,
        "formations_count": 0,
        "genesis_count": 0,
        "formations_panel": {"items": []},
    }


def test_wrap_does_not_touch_world_model_for_has_port(tmp_path, wm, monkeypatch):
    """Draw-path wrap reads only the cache — no get_sector on merge/wrap."""
    wm.results = [1]
    world_model.upsert_sector(
        WORLD,
        {"sector_id": 7, "port": {"last_seen_ts": "t"}},
        state_dir=tmp_path,
    )
    calls = {"n": 0}
    real_get = world_model.get_sector

    def counting_get(*a, **kw):
        calls["n"] += 1
        return real_get(*a, **kw)

    monkeypatch.setattr(world_model, "get_sector", counting_get)
    s = world_stats.WorldStats()
    s.refresh(WORLD, status=_hud_status(7), state_dir=tmp_path)
    assert calls["n"] == 1
    wrapped = s.wrap(lambda: {"ok": True})
    assert wrapped()["has_port"] is True
    assert calls["n"] == 1


# ------------------------------------------------- planet_management (WO-BUILD-COACH-PLANET-MANAGEMENT-TRIGGER-WIRE)


def test_planet_management_omitted_when_no_own_planet(wm):
    wm.results = [1]
    wm.own_planet_landmark_results = [[]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert "planet_management" not in s.merge({"ok": True})


def test_planet_management_true_when_own_planet_landmark_found(wm):
    wm.results = [1]
    wm.own_planet_landmark_results = [[41]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"ok": True})["planet_management"] is True


def test_planet_management_clears_when_later_scan_is_empty(wm):
    wm.results = [1, 1]
    wm.own_planet_landmark_results = [[41], []]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({})["planet_management"] is True
    s.refresh("w-1")
    assert "planet_management" not in s.merge({"ok": True})


def test_planet_management_does_not_clobber_caller(wm):
    wm.results = [1]
    wm.own_planet_landmark_results = [[9]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"planet_management": False})["planet_management"] is False


def test_failed_planet_refresh_keeps_last_observation(wm):
    wm.results = [1, 1]
    wm.own_planet_landmark_results = [[12], RuntimeError("store on fire")]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({})["planet_management"] is True
    s.refresh("w-1")
    assert s.merge({})["planet_management"] is True


# ------------------------------------------------- dead_end_count (WO-COACH-DEAD-END-COUNT)


def test_dead_end_count_omitted_before_refresh(wm):
    s = world_stats.WorldStats()
    assert "dead_end_count" not in s.merge({"ok": True})


def test_dead_end_count_zero_after_empty_completed_scan(wm):
    """Pre-scan omits; completed empty scan reports 0 (not omit)."""
    wm.results = [0]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({})["dead_end_count"] == 0


def test_dead_end_count_counts_one_warp_sectors(wm):
    wm.results = [3]
    wm.sector_lists = [
        [
            {"sector_id": 1, "warps": [2]},
            {"sector_id": 2, "warps": [1, 3]},
            {"sector_id": 3, "warps": []},
            {"sector_id": 4, "warps": [9]},
            {"sector_id": 5},  # missing warps — skip, not invent
        ]
    ]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({})["dead_end_count"] == 2


def test_dead_end_count_does_not_clobber_caller(wm):
    wm.results = [1]
    wm.sector_lists = [[{"sector_id": 1, "warps": [2]}]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({"dead_end_count": 99})["dead_end_count"] == 99


def test_raising_all_sectors_keeps_prior_dead_end_count(wm):
    wm.results = [1, 1]
    wm.sector_lists = [[{"sector_id": 1, "warps": [2]}], RuntimeError("gone")]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert s.merge({})["dead_end_count"] == 1
    s.refresh("w-1")
    assert s.merge({})["dead_end_count"] == 1


def test_hostile_sector_list_never_invents_positive_dead_end_count(wm):
    wm.results = [0]
    wm.sector_lists = [["not-a-dict"]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    assert "dead_end_count" not in s.merge({"ok": True})


def test_wrap_does_not_rescan_dead_ends(wm):
    wm.results = [1]
    wm.sector_lists = [[{"sector_id": 1, "warps": [2]}]]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    n = len(wm.sector_list_calls)
    assert s.wrap(lambda: {})()["dead_end_count"] == 1
    assert len(wm.sector_list_calls) == n



# ------------------------------------------------- formations (WO-FORMATIONS-CATALOG-PORT)


def test_formations_count_equals_genesis_and_panel_len(wm):
    """Dead-end-only catalog: formations_count == genesis_count == panel items."""
    wm.results = [3]
    wm.sector_lists = [
        [
            {"sector_id": 1, "warps": [2]},
            {"sector_id": 2, "warps": [1, 3]},
            {"sector_id": 4, "warps": [9]},
        ]
    ]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    merged = s.merge({})
    assert merged["formations_count"] == 2
    assert merged["genesis_count"] == 2
    assert merged["dead_end_count"] == 2
    items = merged["formations_panel"]["items"]
    assert len(items) == 2
    assert {i["name"] for i in items} == {"Dead-end #1", "Dead-end #4"}


def test_formations_omitted_before_refresh(wm):
    s = world_stats.WorldStats()
    merged = s.merge({"ok": True})
    assert "formations_count" not in merged
    assert "genesis_count" not in merged
    assert "formations_panel" not in merged


def test_world_stats_agrees_with_catalog_world_on_same_sectors(wm):
    """Panel/counts come from formations_from_sectors — same as catalog_world."""
    sectors = [
        {"sector_id": 10, "warps": [11]},
        {"sector_id": 11, "warps": [10, 12]},
        {"sector_id": 12, "warps": [11]},
    ]
    wm.results = [3]
    wm.sector_lists = [sectors]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    merged = s.merge({})
    from tw2002_aiclient import formations

    cat = formations.formations_from_sectors(sectors)
    assert cat is not None
    assert merged["formations_count"] == len(cat.formations)
    assert merged["genesis_count"] == len(cat.genesis_candidates)
    assert merged["formations_panel"]["items"] == formations.panel_items_from_catalog(
        cat
    )


def test_bubble_counts_in_formations_not_dead_end_only(wm):
    """Bubble is genesis/formations; dead_end_count stays out-degree-1 only."""
    wm.results = [5]
    wm.sector_lists = [
        [
            {"sector_id": 1, "warps": [2]},
            {"sector_id": 2, "warps": [1, 10]},
            {"sector_id": 10, "warps": [2, 11, 12]},
            {"sector_id": 11, "warps": [10, 12]},
            {"sector_id": 12, "warps": [10, 11]},
        ]
    ]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    merged = s.merge({})
    # sector 1 is a dead-end; bubble is separate genesis item
    assert merged["dead_end_count"] == 1
    assert merged["formations_count"] == 2  # dead-end + bubble
    assert merged["genesis_count"] == 2
    names = {i["name"] for i in merged["formations_panel"]["items"]}
    assert "Dead-end #1" in names
    assert "Bubble #10" in names


def test_hazard_raises_formations_above_genesis(wm):
    wm.results = [3]
    wm.sector_lists = [
        [
            {"sector_id": 1, "warps": [2]},
            {"sector_id": 2, "warps": [3]},
            {"sector_id": 3, "warps": [2]},
        ]
    ]
    s = world_stats.WorldStats()
    s.refresh("w-1")
    merged = s.merge({})
    # dead-ends at 1? 1 has one warp → dead_end; also one_way 1→2
    # sector 3 has one warp → dead_end
    assert merged["genesis_count"] == merged["dead_end_count"]
    assert merged["formations_count"] > merged["genesis_count"]


def test_world_stats_refresh_writes_formation_membership(tmp_path, monkeypatch):
    """Status refresh stamps membership via write_membership (canon writeback)."""
    from tw2002_aiclient import world_model

    wid = "w-memb"
    world_model.upsert_sector(
        wid, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path
    )
    world_model.upsert_sector(
        wid, {"sector_id": 2, "warps": [1]}, state_dir=tmp_path
    )
    # Point world_stats at real world_model for this test (not FakeWM).
    s = world_stats.WorldStats()
    s.refresh(wid, state_dir=tmp_path)
    rec = world_model.get_sector(wid, 1, state_dir=tmp_path)
    assert "dead-end" in (rec.get("formation_membership") or [])
