"""Pure HUD-panel composer tests (PWO-037, Layer-A).

No curses/terminal involved — asserts the composed lines directly, per the
``tests/test_cockpit_goals.py`` / ``test_cockpit_focus.py`` /
``test_cockpit_decisions.py`` pure-function convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit.hud import (
    FRESHNESS_STALE_S,
    HUD_FIELDS,
    HUD_VALUE_INDENT,
    UNKNOWN_VALUE,
    compose_hud_cells,
    format_freshness,
)

def _iv(text: str) -> str:
    """Expected indented HUD value-row text."""
    return f"{HUD_VALUE_INDENT}{text}"


CANON_LABELS = ["CREDITS", "SECTOR", "TURNS", "CARGO", "PROFIT"]


def _labels(lines):
    return [row[0] for row in lines[0::2]]


def _values(lines):
    return [row[0] for row in lines[1::2]]


def _stales(lines):
    return [row[1] for row in lines[1::2]]


def _tones(lines):
    return [row[2] if len(row) > 2 else None for row in lines[1::2]]


# ---------------------------------------------------------------------------
# format_freshness — thresholds
# ---------------------------------------------------------------------------


def test_freshness_zero_is_now():
    assert format_freshness(0.0) == "✦ now"


def test_freshness_just_under_one_second_is_now():
    assert format_freshness(0.999) == "✦ now"


def test_freshness_exactly_one_second_is_ns_ago():
    assert format_freshness(1.0) == "✦ 1s ago"


def test_freshness_truncates_fractional_seconds():
    assert format_freshness(3.9) == "✦ 3s ago"


def test_freshness_no_minutes_tier_keeps_counting_seconds():
    # Canon cites only "now"/"Ns ago" — the archive never had a minutes/
    # hours tier, and this module doesn't invent one.
    assert format_freshness(3661.0) == "✦ 3661s ago"


def test_freshness_ascii_mark_when_unicode_disabled():
    assert format_freshness(5.0, unicode_ok=False) == "* 5s ago"


def test_freshness_ascii_now_when_unicode_disabled():
    assert format_freshness(0.0, unicode_ok=False) == "* now"


def test_freshness_negative_age_clamps_to_now():
    assert format_freshness(-5.0) == "✦ now"


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), "not-a-number", None, object()])
def test_freshness_never_raises_on_hostile_direct_input(bad):
    # format_freshness is public API — a direct hostile call degrades to
    # the "now" text rather than raising (compose_hud_cells never actually
    # feeds it a non-finite value; see the non-finite age_s tests below).
    assert format_freshness(bad) == "✦ now"


def test_freshness_raising_float_dunder_never_raises():
    class HostileFloat:
        def __float__(self):
            raise RuntimeError("boom")

    assert format_freshness(HostileFloat()) == "✦ now"


# ---------------------------------------------------------------------------
# compose_hud_cells — empty / cold-join state
# ---------------------------------------------------------------------------


def test_status_none_all_ten_lines_unknown():
    lines = compose_hud_cells(None, width=40)
    assert len(lines) == 10
    assert _labels(lines) == CANON_LABELS
    assert _values(lines) == [_iv(UNKNOWN_VALUE)] * 5
    assert _stales(lines) == [False] * 5
    # Label rows are never stale.
    assert all(stale is False for _text, stale, *_rest in lines[0::2])


def test_status_empty_dict_matches_none():
    assert compose_hud_cells({}, width=40) == compose_hud_cells(None, width=40)


def test_status_missing_hud_key_matches_none():
    assert compose_hud_cells({"connected": True}, width=40) == compose_hud_cells(None, width=40)


@pytest.mark.parametrize("bad_status", ["garbage", 5, [1, 2, 3], True])
def test_non_dict_status_never_raises_and_matches_none(bad_status):
    assert compose_hud_cells(bad_status, width=40) == compose_hud_cells(None, width=40)


@pytest.mark.parametrize("bad_hud", ["garbage", 5, [1, 2, 3], None])
def test_non_dict_hud_payload_never_raises_and_matches_none(bad_hud):
    assert compose_hud_cells({"hud": bad_hud}, width=40) == compose_hud_cells(None, width=40)


def test_field_order_and_labels_fixed_regardless_of_hud_key_order():
    status = {
        "hud": {
            "profit": {"value": 1, "age_s": 1.0},
            "credits": {"value": 2, "age_s": 1.0},
            "cargo": {"value": 3, "age_s": 1.0},
            "sector": {"value": 4, "age_s": 1.0},
            "turns": {"value": 5, "age_s": 1.0},
        }
    }
    lines = compose_hud_cells(status, width=40)
    assert _labels(lines) == CANON_LABELS
    assert HUD_FIELDS == ("credits", "sector", "turns", "cargo", "profit")


def test_ten_lines_always_regardless_of_width():
    for width in (0, 1, 5, 10, 40, 80):
        assert len(compose_hud_cells(None, width=width)) == 10


# ---------------------------------------------------------------------------
# Full fixture — exact values, thousands separators, sign
# ---------------------------------------------------------------------------

_FULL_STATUS = {
    "hud": {
        "credits": {"value": 987654, "age_s": 3.0},
        "sector": {"value": 4521, "age_s": 19.999},
        "turns": {"value": 12345, "age_s": 20.0},
        "cargo": {"value": 3, "age_s": 0.0},
        "profit": {"value": -500, "age_s": 0.5},
    }
}


def test_full_fixture_exact_lines():
    lines = compose_hud_cells(_FULL_STATUS, width=40)
    assert lines == [
        ("CREDITS", False, None),
        (_iv("987,654 ✦ 3s ago"), False, None),
        ("SECTOR", False, None),
        (_iv("4521 ✦ 19s ago"), False, None),
        ("TURNS", False, None),
        (_iv("12,345 ✦ 20s ago"), True, None),
        ("CARGO", False, None),
        (_iv("3 ✦ now"), False, None),
        ("PROFIT", False, None),
        (_iv("-500 ✦ now"), False, None),
    ]


def test_positive_profit_gets_explicit_plus_sign():
    status = {"hud": {"profit": {"value": 500, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[9] == (_iv("+500 ✦ 1s ago"), False, None)


def test_sector_and_cargo_render_without_thousands_separator():
    status = {"hud": {"sector": {"value": 12345, "age_s": 1.0}, "cargo": {"value": 6789, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[3] == (_iv("12345 ✦ 1s ago"), False, None)
    assert lines[7] == (_iv("6789 ✦ 1s ago"), False, None)


def test_cargo_empty_total_string_renders_verbatim():
    """Protocol paints empty/total text; composer must not reformat it."""
    status = {
        "hud": {"cargo": {"value": "50 empty / 60", "age_s": 1.0}},
    }
    lines = compose_hud_cells(status, width=40)
    assert lines[7] == (_iv("50 empty / 60 ✦ 1s ago"), False, None)


def test_credits_and_turns_render_with_thousands_separator():
    status = {"hud": {"credits": {"value": 1234567, "age_s": 1.0}, "turns": {"value": 20000, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("1,234,567 ✦ 1s ago"), False, None)
    assert lines[5] == (_iv("20,000 ✦ 1s ago"), False, None)


# ---------------------------------------------------------------------------
# Stale boundary — inclusive on the stale side, only on value rows
# ---------------------------------------------------------------------------


def test_stale_boundary_just_under_threshold_not_stale():
    status = {"hud": {"credits": {"value": 1, "age_s": FRESHNESS_STALE_S - 0.001}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1][1] is False


def test_stale_boundary_exactly_at_threshold_is_stale():
    status = {"hud": {"credits": {"value": 1, "age_s": FRESHNESS_STALE_S}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1][1] is True


def test_stale_boundary_well_past_threshold_is_stale():
    status = {"hud": {"credits": {"value": 1, "age_s": FRESHNESS_STALE_S + 100.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1][1] is True


def test_label_rows_never_stale_even_when_value_row_is():
    status = {"hud": {"credits": {"value": 1, "age_s": 999.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[0] == ("CREDITS", False, None)
    assert lines[1][1] is True


# ---------------------------------------------------------------------------
# Per-cell unknown / partial semantics
# ---------------------------------------------------------------------------


def test_missing_field_is_unknown():
    status = {"hud": {"credits": {"value": 1, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    # sector/turns/cargo/profit all absent
    assert lines[3] == (_iv(UNKNOWN_VALUE), False, None)
    assert lines[5] == (_iv(UNKNOWN_VALUE), False, None)
    assert lines[7] == (_iv(UNKNOWN_VALUE), False, None)
    assert lines[9] == (_iv(UNKNOWN_VALUE), False, None)


def test_value_none_is_unknown_regardless_of_age():
    status = {"hud": {"credits": {"value": None, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv(UNKNOWN_VALUE), False, None)


def test_field_slot_not_a_dict_is_unknown():
    for bad_slot in ["garbage", 5, [1, 2], None, True]:
        status = {"hud": {"credits": bad_slot}}
        lines = compose_hud_cells(status, width=40)
        assert lines[1] == (_iv(UNKNOWN_VALUE), False, None), bad_slot


def test_age_none_renders_value_with_no_stamp_not_stale():
    status = {"hud": {"credits": {"value": 42, "age_s": None}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("42"), False, None)


def test_age_missing_key_renders_value_with_no_stamp():
    status = {"hud": {"credits": {"value": 42}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("42"), False, None)


def test_negative_age_clamps_to_zero_and_reads_now():
    status = {"hud": {"credits": {"value": 42, "age_s": -50.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("42 ✦ now"), False, None)


# ---------------------------------------------------------------------------
# Value coercion — bool / str / non-finite float / hostile objects
# ---------------------------------------------------------------------------


def test_bool_value_renders_as_true_false_text_not_numeric():
    status = {"hud": {"credits": {"value": True, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("True ✦ 1s ago"), False, None)


def test_str_value_renders_verbatim_never_reformatted_as_number():
    status = {"hud": {"credits": {"value": "1234", "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    # No thousands separator inserted -- a string payload is never
    # re-parsed as a number.
    assert lines[1] == (_iv("1234 ✦ 1s ago"), False, None)


def test_str_value_is_trimmed():
    status = {"hud": {"sector": {"value": "  4521  ", "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[3] == (_iv("4521 ✦ 1s ago"), False, None)


def test_whole_valued_float_formats_without_trailing_point_zero():
    status = {"hud": {"credits": {"value": 987654.0, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("987,654 ✦ 1s ago"), False, None)


def test_non_integer_float_value_still_renders():
    status = {"hud": {"credits": {"value": 12.5, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("12.5 ✦ 1s ago"), False, None)


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_value_never_raises_and_degrades_to_unknown(bad):
    status = {"hud": {"credits": {"value": bad, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv(UNKNOWN_VALUE), False, None)


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), "not-a-number", object()])
def test_non_finite_or_unparsable_age_never_raises_and_omits_stamp(bad):
    status = {"hud": {"credits": {"value": 42, "age_s": bad}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("42"), False, None)


def test_raising_str_dunder_on_value_degrades_to_unknown():
    class Boom:
        def __str__(self):
            raise RuntimeError("boom")

        __repr__ = __str__

    status = {"hud": {"credits": {"value": Boom(), "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv(UNKNOWN_VALUE), False, None)


def test_raising_float_dunder_on_age_never_raises():
    class HostileFloat:
        def __float__(self):
            raise RuntimeError("boom")

    status = {"hud": {"credits": {"value": 42, "age_s": HostileFloat()}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv("42"), False, None)


def test_hostile_int_like_value_object_falls_back_to_str():
    class NotReallyInt:
        def __int__(self):
            raise RuntimeError("boom")

        def __str__(self):
            return "weird-42"

    status = {"hud": {"credits": {"value": NotReallyInt(), "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    # Not an int/float instance -- falls straight to the str() fallback,
    # never attempts numeric coercion (and so never triggers __int__).
    assert lines[1] == (_iv("weird-42 ✦ 1s ago"), False, None)


def test_dict_subclass_field_slot_with_hostile_get_is_contained():
    class HostileDict(dict):
        def get(self, key, default=None):
            raise RuntimeError("boom")

    status = {"hud": {"credits": HostileDict(value=1, age_s=1.0)}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1] == (_iv(UNKNOWN_VALUE), False, None)


def test_huge_int_credits_never_raises_and_formats():
    status = {"hud": {"credits": {"value": 10**30, "age_s": 1.0}}}
    lines = compose_hud_cells(status, width=40)
    assert lines[1][0].startswith(_iv("1,000,000"))
    assert lines[1][1] is False


# ---------------------------------------------------------------------------
# Glyph law — unicode_ok swap
# ---------------------------------------------------------------------------


def test_ascii_mark_swap_applies_to_every_stamped_value():
    lines = compose_hud_cells(_FULL_STATUS, width=40, unicode_ok=False)
    for text, *_rest in lines[1::2]:
        assert "✦" not in text
    assert lines[1][0] == _iv("987,654 * 3s ago")


def test_unicode_mark_is_default():
    lines = compose_hud_cells(_FULL_STATUS, width=40)
    assert "✦" in lines[1][0]


# ---------------------------------------------------------------------------
# Width handling
# ---------------------------------------------------------------------------


def test_width_clip_sweep_every_line_within_budget():
    for width in (0, 1, 3, 5, 8, 10, 16, 20, 26, 32, 40, 80):
        lines = compose_hud_cells(_FULL_STATUS, width=width)
        assert len(lines) == 10
        for text, *_rest in lines:
            assert len(text) <= width


def test_width_zero_or_negative_empties_every_line():
    for width in (0, -5):
        lines = compose_hud_cells(_FULL_STATUS, width=width)
        assert [text for text, *_rest in lines] == [""] * 10


def test_width_zero_preserves_stale_flags():
    # Clipping to "" must not silently swallow the stale signal -- the
    # draw layer still needs to know to A_DIM an empty cell.
    status = {"hud": {"credits": {"value": 1, "age_s": 999.0}}}
    lines = compose_hud_cells(status, width=0)
    assert lines[1] == ("", True, None)


def test_width_non_int_never_raises_and_empties():
    lines = compose_hud_cells(_FULL_STATUS, width="not-a-number")
    assert [text for text, *_rest in lines] == [""] * 10


def test_width_none_never_raises_and_empties():
    lines = compose_hud_cells(_FULL_STATUS, width=None)
    assert [text for text, *_rest in lines] == [""] * 10


@pytest.mark.parametrize("bad_width", [float("inf"), float("-inf"), float("nan")])
def test_width_non_finite_float_never_raises_and_empties(bad_width):
    # int(float("inf")) raises OverflowError, not TypeError/ValueError --
    # and a bare `Infinity`/`-Infinity`/`NaN` literal is valid JSON per
    # json.loads()'s default parsing, so a hostile wire width can
    # legitimately arrive as exactly this float.
    lines = compose_hud_cells(_FULL_STATUS, width=bad_width)
    assert len(lines) == 10
    assert [text for text, *_rest in lines] == [""] * 10


def test_narrow_width_clips_mid_value():
    status = {"hud": {"credits": {"value": 987654, "age_s": 3.0}}}
    lines = compose_hud_cells(status, width=5)
    assert lines[1][0] == "  987"
    assert len(lines[1][0]) == 5

# ---------------------------------------------------------------------------
# TURNS fuel-gauge (WO-BUILD-TURNS-FUEL-GAUGE-MAX-ACCUMULATOR)
# ---------------------------------------------------------------------------


def test_turns_without_turns_max_stays_numeric_only():
    status = {
        "hud": {
            "turns": {"value": 850, "age_s": 0.0},
        }
    }
    lines = compose_hud_cells(status, width=60)
    turns_value = _values(lines)[2]
    assert "[" not in turns_value
    assert _tones(lines)[2] is None


def test_turns_with_turns_max_appends_gauge_and_ok_tone():
    status = {
        "hud": {
            "turns": {"value": 1000, "age_s": 0.0, "turns_max": 1000},
        }
    }
    lines = compose_hud_cells(status, width=60)
    turns_value = _values(lines)[2]
    assert "[██████████]" in turns_value
    assert _tones(lines)[2] == "ok"


def test_turns_gauge_warn_and_danger_thresholds():
    warn_status = {
        "hud": {"turns": {"value": 300, "age_s": 1.0, "turns_max": 1000}}
    }
    danger_status = {
        "hud": {"turns": {"value": 100, "age_s": 1.0, "turns_max": 1000}}
    }
    assert _tones(compose_hud_cells(warn_status, width=60))[2] == "warn"
    assert _tones(compose_hud_cells(danger_status, width=60))[2] == "danger"


def test_turns_gauge_ascii_twin_when_unicode_disabled():
    status = {
        "hud": {"turns": {"value": 500, "age_s": 0.0, "turns_max": 1000}}
    }
    lines = compose_hud_cells(status, width=60, unicode_ok=False)
    turns_value = _values(lines)[2]
    assert "[#####.....]" in turns_value
    assert "█" not in turns_value


def test_turns_max_zero_or_missing_skips_gauge():
    for tmax in (0, None, False, "nope", float("nan")):
        cell = {"value": 50, "age_s": 0.0}
        if tmax is not None:
            cell["turns_max"] = tmax
        lines = compose_hud_cells({"hud": {"turns": cell}}, width=60)
        assert "[" not in _values(lines)[2]
        assert _tones(lines)[2] is None


def test_render_bar_meter_clamps_and_width():
    from tw2002_aiclient.cockpit.hud import render_bar_meter

    assert render_bar_meter(1.5, 10) == "[██████████]"
    assert render_bar_meter(-0.3, 10) == "[░░░░░░░░░░]"
    assert render_bar_meter(0.5, 10) == "[█████░░░░░]"
