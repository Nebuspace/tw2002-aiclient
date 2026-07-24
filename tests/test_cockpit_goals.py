"""Pure GOALS-panel composer tests (PWO-034, Layer-A).

No curses/terminal involved — asserts the composed lines directly, per the
``tests/test_cockpit_strip.py`` pure-function convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit.goals import (
    GLYPH_BLOCKED,
    GLYPH_MET,
    GLYPH_PARTIAL,
    GLYPH_UNKNOWN,
    UNKNOWN_DETAIL,
    compose_goals_lines,
)

CANON_LABELS = (
    "Turns",
    "Credits",
    "StarDock",
    "Map",
    "Formations",
    "Chain",
    "Ship prices",
    "Hold price",
    "Fighters",
)


# ---------------------------------------------------------------------------
# Empty / cold-join state — every row honest-unknown, nothing vanishes
# ---------------------------------------------------------------------------


def test_status_none_all_nine_lines_unknown():
    lines = compose_goals_lines(None, width=40)
    assert lines == [
        "? Turns —",
        "? Credits —",
        "? StarDock —",
        "? Map —",
        "? Formations —",
        "? Chain —",
        "? Ship prices —",
        "? Hold price —",
        "? Fighters —",
    ]


def test_status_empty_dict_matches_none():
    assert compose_goals_lines({}, width=40) == compose_goals_lines(None, width=40)


def test_empty_state_never_vanishes_rows():
    lines = compose_goals_lines(None, width=40)
    assert len(lines) == 9
    for label in CANON_LABELS:
        assert any(label in line for line in lines), label


# ---------------------------------------------------------------------------
# Full fixture — exact lines at a wide and a narrow (short-label) width
# ---------------------------------------------------------------------------

_FULL_STATUS = {
    "turns_left": 12345,
    "credits": 987654,
    "stardock_sectors": [10, 42, 7, 99],
    "known_sectors": 30,
    "galaxy_size": 100,
    "formations_count": 3,
    "chain_hops": 5,
    "chain_unit": "hops",
    "ship_prices_count": 4,
    "hold_price_label": "1,200cr",
    "fighters_aboard": 10,
}


def test_full_fixture_wide_width_exact_lines():
    lines = compose_goals_lines(_FULL_STATUS, width=40)
    assert lines == [
        "✓ Turns 12,345",
        "✓ Credits 987,654",
        "✓ StarDock @10,42,7",
        "· Map 30/100 (30%)",
        "· Formations 3 found",
        "✓ Chain 5 hops",
        "✓ Ship prices 4 priced",
        "✓ Hold price 1,200cr",
        "✓ Fighters 10",
    ]


def test_full_fixture_narrow_width_uses_short_labels():
    status = dict(_FULL_STATUS, stardock_sectors=[10, 42])
    lines = compose_goals_lines(status, width=20)
    assert lines == [
        "✓ Trn 12,345",
        "✓ Cr 987,654",
        "✓ Dock @10,42",
        "· Map 30/100",
        "· Form 3 found",
        "✓ Chain 5 h",
        "✓ Ships 4 ok",
        "✓ Hold 1,200cr",
        "✓ Ftr 10",
    ]


def test_canon_order_is_fixed_regardless_of_dict_key_order():
    reordered = dict(reversed(list(_FULL_STATUS.items())))
    assert compose_goals_lines(reordered, width=40) == compose_goals_lines(_FULL_STATUS, width=40)


# ---------------------------------------------------------------------------
# Per-field partial fixtures
# ---------------------------------------------------------------------------


def test_stardock_not_found_blocks_ship_and_hold_price():
    lines = compose_goals_lines({"stardock_found": False}, width=40)
    assert lines[2] == "· StarDock not found"
    assert lines[6] == f"{GLYPH_BLOCKED} Ship prices {UNKNOWN_DETAIL}"
    assert lines[7] == f"{GLYPH_BLOCKED} Hold price {UNKNOWN_DETAIL}"


def test_stardock_unknown_does_not_block_ship_and_hold_price():
    # Unresolved StarDock status (key absent) is honest-unknown, not a
    # confirmed negative search — Ship prices/Hold price must not claim
    # they're blocked on a state we never actually observed.
    lines = compose_goals_lines({}, width=40)
    assert lines[2] == f"? StarDock {UNKNOWN_DETAIL}"
    assert lines[6] == f"? Ship prices {UNKNOWN_DETAIL}"
    assert lines[7] == f"? Hold price {UNKNOWN_DETAIL}"


def test_stardock_found_without_sectors_list():
    lines = compose_goals_lines({"stardock_found": True}, width=40)
    assert lines[2] == "✓ StarDock found"


def test_stardock_sectors_list_caps_at_three():
    lines = compose_goals_lines({"stardock_sectors": [1, 2, 3, 4, 5]}, width=40)
    assert lines[2] == "✓ StarDock @1,2,3"


def test_map_known_sectors_without_galaxy_size():
    lines = compose_goals_lines({"known_sectors": 17}, width=40)
    assert lines[3] == "· Map 17 sectors"


def test_map_fully_explored_shows_met_glyph():
    lines = compose_goals_lines({"known_sectors": 100, "galaxy_size": 100}, width=40)
    assert lines[3] == "✓ Map 100/100 (100%)"


def test_formations_zero_is_unknown_glyph_not_partial():
    # A confirmed-zero count reads the same as never having asked — the
    # composer can't distinguish "searched, found none" from "never
    # searched" without a separate found-flag, so it stays honest ?.
    lines = compose_goals_lines({"formations_count": 0}, width=40)
    assert lines[4] == "? Formations 0 found"


def test_formations_positive_is_partial_glyph():
    lines = compose_goals_lines({"formations_count": 2}, width=40)
    assert lines[4] == "· Formations 2 found"


def test_chain_zero_hops_is_partial_not_unknown():
    lines = compose_goals_lines({"chain_hops": 0}, width=40)
    assert lines[5] == "· Chain none yet"


def test_ship_prices_zero_is_partial_price_unknown():
    lines = compose_goals_lines({"ship_prices_count": 0}, width=40)
    assert lines[6] == "· Ship prices price?"


def test_hold_price_blank_string_key_present_is_partial():
    lines = compose_goals_lines({"hold_price_label": ""}, width=40)
    assert lines[7] == "· Hold price price?"


def test_fighters_zero_shows_default_buy_status():
    lines = compose_goals_lines({"fighters_aboard": 0}, width=40)
    assert lines[8] == "· Fighters 0 (need some)"


def test_fighters_zero_shows_supplied_buy_status():
    lines = compose_goals_lines(
        {"fighters_aboard": 0, "fighter_buy_status": "afford 3"}, width=40
    )
    assert lines[8] == "· Fighters 0 (afford 3)"


def test_fighters_positive_count():
    lines = compose_goals_lines({"fighters_aboard": 10}, width=40)
    assert lines[8] == "✓ Fighters 10"


# ---------------------------------------------------------------------------
# Malformed input — never raises, always degrades to honest unknown
# ---------------------------------------------------------------------------


def test_malformed_values_never_raise_and_degrade_to_unknown():
    status = {
        "turns_left": "abc",
        "credits": [1, 2, 3],
        "stardock_sectors": "not-a-list",
        "known_sectors": {},
        "formations_count": None,
        "chain_hops": object(),
        "ship_prices_count": "xx",
        "hold_price_label": 12345,  # coerces to a real (if odd) label
        "fighters_aboard": "3.5",
    }
    lines = compose_goals_lines(status, width=40)
    assert len(lines) == 9
    assert lines[0] == f"? Turns {UNKNOWN_DETAIL}"
    assert lines[1] == f"? Credits {UNKNOWN_DETAIL}"
    assert lines[2] == f"? StarDock {UNKNOWN_DETAIL}"
    assert lines[3] == f"? Map {UNKNOWN_DETAIL}"
    assert lines[4] == f"? Formations {UNKNOWN_DETAIL}"
    assert lines[5] == f"? Chain {UNKNOWN_DETAIL}"
    assert lines[6] == f"? Ship prices {UNKNOWN_DETAIL}"
    assert lines[7] == "✓ Hold price 12345"
    assert lines[8] == f"? Fighters {UNKNOWN_DETAIL}"


_INT_BACKED_FIELDS = (
    "turns_left",
    "credits",
    "known_sectors",
    "galaxy_size",
    "formations_count",
    "chain_hops",
    "ship_prices_count",
    "fighters_aboard",
)


@pytest.mark.parametrize("field", _INT_BACKED_FIELDS)
@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_float_on_every_int_field_never_raises(field, bad):
    # Regression: json.loads accepts bare Infinity/-Infinity/NaN by default
    # (allow_nan=True) — int(float('inf')) raises OverflowError, not
    # ValueError/TypeError, so a malformed daemon payload carrying a
    # non-finite float on any of these keys must still degrade to the
    # honest all-unknown render, never crash the composer.
    lines = compose_goals_lines({field: bad}, width=40)
    assert lines == compose_goals_lines({}, width=40)


def test_stardock_sectors_entry_with_raising_str_never_raises():
    class Boom:
        def __str__(self):
            raise RuntimeError("boom")

        __repr__ = __str__

    lines = compose_goals_lines({"stardock_sectors": [Boom(), 5]}, width=40)
    assert lines[2] == "✓ StarDock @?,5"


def test_status_non_dict_types_never_raise():
    for bad in ("a string", 12345, 3.14, [1, 2, 3], object(), True):
        lines = compose_goals_lines(bad, width=40)
        assert lines == compose_goals_lines(None, width=40)


def test_width_non_int_never_raises():
    lines = compose_goals_lines({"turns_left": 5}, width="not-a-number")
    assert lines == [""] * 9


# ---------------------------------------------------------------------------
# Width handling
# ---------------------------------------------------------------------------


def test_width_clip_sweep_every_line_within_budget():
    for width in (0, 1, 5, 8, 10, 16, 20, 26, 32, 40, 80):
        lines = compose_goals_lines(_FULL_STATUS, width=width)
        assert len(lines) == 9
        for line in lines:
            assert len(line) <= width


def test_width_zero_or_negative_returns_all_empty_lines():
    assert compose_goals_lines(_FULL_STATUS, width=0) == [""] * 9
    assert compose_goals_lines(_FULL_STATUS, width=-5) == [""] * 9


def test_narrow_width_switches_every_label_to_short_form():
    lines = compose_goals_lines(_FULL_STATUS, width=25)
    long_only = {"StarDock", "Formations", "Ship prices", "Hold price", "Fighters"}
    for line in lines:
        assert not any(label in line for label in long_only)


# ---------------------------------------------------------------------------
# Glyph-set pin — only the canon four status glyphs, never a fabrication
# ---------------------------------------------------------------------------


def test_glyph_set_pin_no_ascii_fabrications():
    canon_glyphs = {GLYPH_MET, GLYPH_PARTIAL, GLYPH_UNKNOWN, GLYPH_BLOCKED}
    assert canon_glyphs == {"✓", "·", "?", "⊘"}

    fixtures = [
        None,
        {},
        _FULL_STATUS,
        {"stardock_found": False},
        {"formations_count": 0},
        {"chain_hops": 0},
        {"fighters_aboard": 0},
        {"hold_price_label": ""},
    ]
    for status in fixtures:
        for line in compose_goals_lines(status, width=40):
            if not line:
                continue
            leading_glyph = line[0]
            assert leading_glyph in canon_glyphs, line
            assert leading_glyph not in {"x", "-", "|"}, line
    # No fabricated ASCII twins anywhere in a full-fixture render either.
    for line in compose_goals_lines(_FULL_STATUS, width=40):
        assert "x" != line[0]
