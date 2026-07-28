"""chain_detect_view tests -- the pure formatter over `chain_detect`'s
typed payload (WO-CHAIN-DETECT-WIRE re-scope, 2026-07-28).

`chain_detect.recompute`'s own pairing/staleness/routing/ranking logic is
pinned in `test_trade_adapter.py` and `test_chain_detect.py`; this file
pins only the render layer: `format_candidate_pair_lines`. Fixtures use a
small duck-typed `_Payload`/`_Pair` stand-in rather than the real
`chain_detect.PairLoopResult`/`trade_adapter.CandidatePair` for most
cases -- the module under test never imports either (see its own
docstring: `getattr`-only, matching `cockpit/chains.py::compose_chain_lines`'s
own discipline) -- with one end-to-end test wiring the real objects to
prove the duck-typing genuinely lines up with the real shape.
"""

from __future__ import annotations

import datetime

import pytest

from tw2002_aiclient import chain_detect, chain_detect_view, trade_adapter, world_model
from tw2002_aiclient.cockpit import chains as cockpit_chains

WORLD = "hostA__F__ALPHA"
_CLOCK = lambda: datetime.datetime(2026, 7, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _upsert_class(tmp_path, sector_id, *, warps=(), klass=None, port_ts_clock=_CLOCK):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if klass is not None:
        record["port"] = {"class": klass, "last_seen_ts": world_model._now_iso(port_ts_clock)}
    world_model.upsert_sector(WORLD, record, state_dir=tmp_path, now=port_ts_clock)


class _Pair:
    """Duck-typed `CandidatePair` stand-in -- every field the formatter
    reads, nothing it doesn't need."""

    def __init__(self, sector_a, sector_b, commodities_a_sells, commodities_b_sells, turns):
        self.sector_a = sector_a
        self.sector_b = sector_b
        self.commodities_a_sells = commodities_a_sells
        self.commodities_b_sells = commodities_b_sells
        self.turns = turns


class _Payload:
    """Duck-typed `PairLoopResult` stand-in."""

    def __init__(self, pairs=(), reason=None, detail=None):
        self.pairs = pairs
        self.reason = reason
        self.detail = detail


_ONE_PAIR = _Payload(pairs=(_Pair(10, 11, ("Fuel Ore",), ("Organics", "Equipment"), 2),))
_TWO_PAIRS = _Payload(
    pairs=(
        _Pair(10, 11, ("Fuel Ore",), ("Organics", "Equipment"), 2),
        _Pair(20, 22, ("Fuel Ore",), ("Equipment",), 4),
    )
)


# --------------------------------------------------------------------------
# Basic shape
# --------------------------------------------------------------------------


def test_title_is_first_line():
    lines = chain_detect_view.format_candidate_pair_lines(_ONE_PAIR)
    assert lines[0] == chain_detect_view.TITLE


def test_row_carries_sectors_and_full_commodity_sets():
    (row,) = chain_detect_view.format_candidate_pair_lines(_ONE_PAIR, width=80)[1:]
    assert "10<->11" in row
    assert "Fuel Ore" in row
    # REVISE: the full set survives, never collapsed to one pick.
    assert "Organics" in row
    assert "Equipment" in row


def test_multi_commodity_set_never_collapsed_to_a_single_pick():
    """Direct pin on the fix that removed `min()`'s tiebreak entirely --
    both compatible commodities on the B-side must render, not just one."""
    payload = _Payload(pairs=(_Pair(1, 2, ("Fuel Ore",), ("Organics", "Equipment"), 2),))
    (row,) = chain_detect_view.format_candidate_pair_lines(payload, width=80)[1:]
    assert "Organics" in row and "Equipment" in row


def test_best_pair_marked_others_not():
    lines = chain_detect_view.format_candidate_pair_lines(_TWO_PAIRS, width=80)
    assert lines[1].startswith(chain_detect_view.BEST_UNICODE)
    assert not lines[2].startswith(chain_detect_view.BEST_UNICODE)


def test_end_to_end_with_real_recompute_output(tmp_path):
    """The duck-typing genuinely matches the real objects -- not just the
    hand-built `_Pair`/`_Payload` stand-ins above."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")
    result = chain_detect.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)

    lines = chain_detect_view.format_candidate_pair_lines(result)

    assert lines[0] == chain_detect_view.TITLE
    assert "10<->11" in lines[1]
    assert "2t" in lines[1]


# --------------------------------------------------------------------------
# The empty state -- distinguishable from cockpit/chains.py's taught-loop
# placeholder (Samantha REVISE requirement, 2026-07-28).
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        chain_detect.REASON_NO_WORLD_MODEL,
        chain_detect.REASON_FEWER_THAN_TWO_PORTS,
        chain_detect.REASON_ALL_STALE,
        chain_detect.REASON_NO_COMPATIBLE_PAIRS,
        chain_detect.REASON_COMPATIBLE_BUT_UNROUTED,
    ],
)
def test_empty_result_is_never_the_taught_loop_placeholder(reason):
    """Pin #4 -- mutation-proven (see report): a discovered-pairs empty
    must never render as, or be mistaken for, `cockpit/chains.py`'s
    canon-bound `○ ○  no trade loop yet`. Every one of the five typed
    reasons is checked, not just one, since a formatter bug could plausibly
    only mis-render a subset."""
    payload = _Payload(pairs=(), reason=reason, detail=None)
    body = "\n".join(chain_detect_view.format_candidate_pair_lines(payload))
    assert cockpit_chains.EMPTY_TEXT not in body
    assert cockpit_chains.EMPTY_UNICODE not in body


def test_empty_result_uses_the_unknown_glyph_and_reason_text():
    payload = _Payload(pairs=(), reason=chain_detect.REASON_NO_COMPATIBLE_PAIRS, detail=None)
    lines = chain_detect_view.format_candidate_pair_lines(payload)
    assert lines == [chain_detect_view.TITLE, f"{chain_detect_view.UNKNOWN}  no compatible postures"]


def test_empty_result_carries_detail_when_present():
    payload = _Payload(pairs=(), reason=chain_detect.REASON_ALL_STALE, detail="oldest class reading is 5s old")
    (line,) = chain_detect_view.format_candidate_pair_lines(payload)[1:]
    assert "class data too old" in line
    assert "oldest class reading is 5s old" in line


def test_unrecognized_reason_still_degrades_honestly():
    payload = _Payload(pairs=(), reason="not_a_real_reason", detail=None)
    (line,) = chain_detect_view.format_candidate_pair_lines(payload)[1:]
    assert chain_detect_view.UNKNOWN in line
    assert "no discovered pair loops" in line


# --------------------------------------------------------------------------
# Pin 1 -- no fabricated keystroke-step count is EVER rendered.
# Mutation: add a "N steps"-shaped fragment to the row -- must go red.
# --------------------------------------------------------------------------


def test_no_keystroke_step_count_ever_rendered():
    import re

    lines = chain_detect_view.format_candidate_pair_lines(_TWO_PAIRS, width=80)
    body = "\n".join(lines)
    assert re.search(r"\d+\s*steps?\b", body) is None


# --------------------------------------------------------------------------
# Pin 2 -- `turns` reaches rendered output, and is never truncated away
# even at the narrowest supported width.
# Mutation: drop `turns_text` from the row -- must go red.
# --------------------------------------------------------------------------


def test_turns_reaches_output_at_default_width():
    (row,) = chain_detect_view.format_candidate_pair_lines(_ONE_PAIR)[1:]
    assert "2t" in row


def test_turns_survives_even_at_the_narrowest_width():
    (row,) = chain_detect_view.format_candidate_pair_lines(_ONE_PAIR, width=1)[1:]
    assert "2t" in row  # width is clamped to a floor of 12, but turns must still show whole


# --------------------------------------------------------------------------
# Pin 3 -- the provenance tag fits its own declared column width, and
# never truncates away either (same "protected field" discipline as turns).
# Mutation: lengthen SOURCE_TAG past its ceiling -- must go red.
# --------------------------------------------------------------------------


def test_source_tag_fits_its_declared_width_constant():
    """Checked against the REAL constant, never a restated number."""
    assert len(chain_detect_view.SOURCE_TAG) <= chain_detect_view._SOURCE_TAG_MAX_W


def test_source_tag_reaches_output_and_is_never_recorded_or_mined():
    (row,) = chain_detect_view.format_candidate_pair_lines(_ONE_PAIR)[1:]
    assert chain_detect_view.SOURCE_TAG in row
    assert "recorded" not in row
    assert "mined" not in row


def test_source_tag_survives_even_at_the_narrowest_width():
    (row,) = chain_detect_view.format_candidate_pair_lines(_ONE_PAIR, width=1)[1:]
    assert chain_detect_view.SOURCE_TAG in row


# --------------------------------------------------------------------------
# Pin 4 -- covered above (test_empty_result_is_never_the_taught_loop_placeholder)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Pin 5 -- never raises, regardless of payload shape.
# Mutation: remove the `isinstance(pairs, (tuple, list))` guard -- must go red.
# --------------------------------------------------------------------------


def test_never_raises_on_a_malformed_payload():
    for bogus in (None, 7, "payload", object(), {}, [], _Payload(pairs="not-a-list")):
        assert chain_detect_view.format_candidate_pair_lines(bogus)


def test_never_raises_on_malformed_pairs_inside_a_well_shaped_payload():
    payload = _Payload(pairs=("not-a-pair", 42, None, object()))
    lines = chain_detect_view.format_candidate_pair_lines(payload, width=80)
    assert len(lines) == 5  # TITLE + 4 garbage rows, each degraded not raised
    for row in lines[1:]:
        assert chain_detect_view.UNKNOWN in row


def test_never_raises_on_bad_width_or_unicode_ok():
    for bogus_width in (None, "wide", -5, object()):
        assert chain_detect_view.format_candidate_pair_lines(_ONE_PAIR, width=bogus_width)
    for bogus_unicode_ok in (None, "yes", 0, 1):
        assert chain_detect_view.format_candidate_pair_lines(_ONE_PAIR, unicode_ok=bogus_unicode_ok)


# --------------------------------------------------------------------------
# Pin 6 -- unicode_ok=False yields an all-ASCII line; the unicode ★ never
# leaks through. Mutation: hardcode BEST_UNICODE regardless of the flag --
# must go red.
# --------------------------------------------------------------------------


def test_ascii_mode_yields_the_ascii_marker_and_no_unicode_leak():
    lines = chain_detect_view.format_candidate_pair_lines(_TWO_PAIRS, unicode_ok=False, width=80)
    body = "\n".join(lines)
    assert lines[1].startswith(chain_detect_view.BEST_ASCII)
    assert chain_detect_view.BEST_UNICODE not in body
    assert body.isascii()


def test_unicode_mode_uses_the_real_glyph():
    lines = chain_detect_view.format_candidate_pair_lines(_TWO_PAIRS, unicode_ok=True, width=80)
    assert lines[1].startswith(chain_detect_view.BEST_UNICODE)
