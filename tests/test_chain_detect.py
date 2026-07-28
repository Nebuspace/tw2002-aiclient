"""chain_detect tests -- the wired `recompute` surface (WO-CHAIN-DETECT-WIRE).
Synthetic world-model fixtures only, same tmp_path/state_dir convention as
`test_trade_adapter.py` and `world_model`'s own tests -- no live daemon,
no network.

`build_candidate_pairs`'s own pairing/staleness/routing logic (including
every typed-empty-reason TRIGGER condition) is pinned in
`test_trade_adapter.py`; this file pins the layer ABOVE it: ranking,
idempotency, and the `PairLoopResult` shape.

Render-side tests (the pure formatter over this module's output) live in
`test_chain_detect_view.py`, not here -- `chain_detect.py` itself no
longer renders anything (hub re-scope, 2026-07-28: the earlier
`as_library_rows` bridge into `loops/list_view.format_loop_row` was
deleted, not repaired; see `chain_detect.py`'s own module docstring).
"""

from __future__ import annotations

import datetime

import pytest

from tw2002_aiclient import chain_detect, trade_adapter, world_model

WORLD = "hostA__F__ALPHA"

_CLOCK = lambda: datetime.datetime(2026, 7, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _upsert_class(tmp_path, sector_id, *, warps=(), klass=None, port_ts_clock=_CLOCK):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if klass is not None:
        record["port"] = {"class": klass, "last_seen_ts": world_model._now_iso(port_ts_clock)}
    world_model.upsert_sector(WORLD, record, state_dir=tmp_path, now=port_ts_clock)


def test_recompute_ranks_by_turns_ascending_then_sector_pair(tmp_path):
    """Three ports, two disjoint pairs at different round-trip turns:
    (10, 11) is adjacent (turns == 2); (20, 22) requires a waypoint at
    21 each way (turns == 4). The cheaper pair must rank first --
    canon's H1, "an adjacent pair is the cheapest shape"."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")
    _upsert_class(tmp_path, 20, warps=(21,), klass="SBB")
    _upsert_class(tmp_path, 21, warps=(20, 22))
    _upsert_class(tmp_path, 22, warps=(21,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert result.reason is None
    assert [(p.sector_a, p.sector_b) for p in result.pairs] == [(10, 11), (20, 22)]
    assert [p.turns for p in result.pairs] == [2, 4]


def test_recompute_ties_on_turns_break_by_sector_pair_ascending(tmp_path):
    """Two disjoint pairs, both adjacent (turns == 2 each) -- the tie
    breaks on `(sector_a, sector_b)` ascending, a real total order, not
    build/dict-iteration order."""
    _upsert_class(tmp_path, 50, warps=(51,), klass="SBB")
    _upsert_class(tmp_path, 51, warps=(50,), klass="BSS")
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert [(p.sector_a, p.sector_b) for p in result.pairs] == [(10, 11), (50, 51)]


@pytest.mark.parametrize(
    "reason_const",
    [
        chain_detect.REASON_NO_WORLD_MODEL,
        chain_detect.REASON_FEWER_THAN_TWO_PORTS,
        chain_detect.REASON_ALL_STALE,
        chain_detect.REASON_NO_COMPATIBLE_PAIRS,
        chain_detect.REASON_COMPATIBLE_BUT_UNROUTED,
    ],
)
def test_every_reason_constant_is_a_distinct_string(reason_const):
    assert isinstance(reason_const, str) and reason_const


def test_recompute_no_world_model(tmp_path):
    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    assert result.pairs == ()
    assert result.reason == chain_detect.REASON_NO_WORLD_MODEL
    assert result.detail is None


def test_recompute_fewer_than_two_ports(tmp_path):
    _upsert_class(tmp_path, 1, warps=(2,))
    _upsert_class(tmp_path, 2, warps=(1,), klass="SBB")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert result.pairs == ()
    assert result.reason == chain_detect.REASON_FEWER_THAN_TWO_PORTS
    assert result.detail is None


def test_recompute_all_stale_detail_carries_a_real_age(tmp_path):
    old_clock = lambda: datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB", port_ts_clock=old_clock)
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS", port_ts_clock=old_clock)

    cfg = trade_adapter.PairLoopConfig(class_max_age_s=10.0)
    result = chain_detect.recompute(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert result.pairs == ()
    assert result.reason == chain_detect.REASON_ALL_STALE
    expected_age = (_CLOCK() - old_clock()).total_seconds()
    assert result.detail == f"oldest class reading is {expected_age:.0f}s old"


def test_recompute_no_compatible_pairs(tmp_path):
    _upsert_class(tmp_path, 20, warps=(21,), klass="SSS")
    _upsert_class(tmp_path, 21, warps=(20,), klass="SSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert result.pairs == ()
    assert result.reason == chain_detect.REASON_NO_COMPATIBLE_PAIRS


def test_recompute_compatible_but_unrouted(tmp_path):
    _upsert_class(tmp_path, 30, warps=(), klass="SBB")
    _upsert_class(tmp_path, 31, warps=(), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert result.pairs == ()
    assert result.reason == chain_detect.REASON_COMPATIBLE_BUT_UNROUTED


def test_recompute_is_idempotent_same_disk_state_same_injected_now(tmp_path):
    """Same on-disk state, same injected `now` -> byte-identical result
    across two calls -- DoD accept 2. A wall-clock `now` straddling the
    staleness boundary would make this flaky; `now` is injected here
    for exactly that reason."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")
    _upsert_class(tmp_path, 20, warps=(21,), klass="SSS")
    _upsert_class(tmp_path, 21, warps=(20,), klass="SSS")

    first = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    second = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert first == second


def test_recompute_idempotent_on_a_typed_empty_too(tmp_path):
    first = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    second = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    assert first == second == chain_detect.PairLoopResult(
        world_id=WORLD, pairs=(), reason=chain_detect.REASON_NO_WORLD_MODEL, detail=None
    )
