"""chain_detect tests -- the wired `recompute`/`as_library_rows` surface
(WO-CHAIN-DETECT-WIRE). Synthetic world-model fixtures only, same
tmp_path/state_dir convention as `test_trade_adapter.py` and
`world_model`'s own tests -- no live daemon, no network.

`build_candidate_pairs`'s own pairing/staleness/routing logic (including
every typed-empty-reason TRIGGER condition) is pinned in
`test_trade_adapter.py`; this file pins the layer ABOVE it: ranking,
idempotency, the `PairLoopResult` shape, and the bridge into
`loops/list_view.format_loop_row`.
"""

from __future__ import annotations

import datetime

import pytest

from tw2002_aiclient import chain_detect, trade_adapter, world_model
from tw2002_aiclient.loops import list_view

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


# --------------------------------------------------------------------------
# Bridge into loops/list_view.format_loop_row -- listing rows ONLY, never
# cockpit/chains.py or its taught-macro arm store (module docstring's hard
# prohibition; that module is not imported anywhere in this file's closure).
# --------------------------------------------------------------------------


def test_as_library_rows_matches_format_loop_row_exactly(tmp_path):
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    rows = chain_detect.as_library_rows(result)

    assert len(result.pairs) == 1
    pair = result.pairs[0]
    expected = list_view.format_loop_row(
        {"name": f"10<->11 ({pair.turns}t)", "source": chain_detect._SOURCE_TAG}
    )
    assert rows == [expected]


def test_as_library_rows_never_carries_a_profit_key(tmp_path):
    """`CandidatePair` has no margin field at all -- confirm the bridge
    never invents one, and that `format_loop_row` renders canon's
    em-dash (never a fabricated `0`) for the absent profit."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    (row,) = chain_detect.as_library_rows(result)

    assert list_view.UNKNOWN_VALUE in row
    assert "0cr" not in row


# --------------------------------------------------------------------------
# Samantha REVISE (see chain_detect.py / as_library_rows docstring history):
# the first draft emitted a fabricated `"steps": 2` (a HOP count rendered
# through a column that means recorded/mined KEYSTROKE steps) and silently
# dropped `pair.turns`, the one real number on the row. Three pins below,
# each proven against a scratch mutant of the real source (never the
# working tree) -- see report Verification for the exact mutation + result.
# --------------------------------------------------------------------------


def test_discovered_row_never_renders_a_fabricated_step_count(tmp_path):
    """A pair loop has never been recorded, so it has ZERO keystroke
    steps, not two hops rendered as `"2 steps"`. The row must show
    `format_loop_row`'s own honest-unknown text for a hand-built row
    that never supplies `steps` -- never a plausible-looking digit.
    Mutation: reintroducing `"steps": 2` into the row dict inside
    `as_library_rows` turns this red (see report)."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    (row,) = chain_detect.as_library_rows(result)

    assert f"{list_view.UNKNOWN} steps" in row
    assert "2 steps" not in row


def test_pair_turns_survives_into_the_rendered_row(tmp_path):
    """`pair.turns` is the one genuinely-known, never-fabricated number
    on this row -- it must reach the rendered string somewhere.
    Mutation: dropping `pair.turns` from the `name` f-string inside
    `as_library_rows` turns this red (see report)."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    (row,) = chain_detect.as_library_rows(result)
    pair = result.pairs[0]

    assert pair.turns == 2  # sanity: a genuinely non-trivial figure, not a coincidental 0/1
    assert f"({pair.turns}t)" in row


def test_source_tag_fits_the_list_view_source_column_width():
    """Width-pinned against the REAL constant, never a restated `9` --
    a future rename of `list_view._SOURCE_W` re-checks itself here
    automatically. Mutation: widening `chain_detect._SOURCE_TAG` past
    9 characters (e.g. back to `"discovered"`, 10 chars) turns this red
    (see report)."""
    assert len(chain_detect._SOURCE_TAG) <= list_view._SOURCE_W


def test_as_library_rows_preserves_ranked_order(tmp_path):
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")
    _upsert_class(tmp_path, 20, warps=(21,), klass="SBB")
    _upsert_class(tmp_path, 21, warps=(20, 22))
    _upsert_class(tmp_path, 22, warps=(21,), klass="BSS")

    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    rows = chain_detect.as_library_rows(result)

    assert len(rows) == 2
    assert rows[0].startswith("10<->11")
    assert rows[1].startswith("20<->22")


def test_as_library_rows_empty_on_a_typed_empty_result():
    empty = chain_detect.PairLoopResult(
        world_id=WORLD, pairs=(), reason=chain_detect.REASON_NO_WORLD_MODEL, detail=None
    )
    assert chain_detect.as_library_rows(empty) == []
