"""Pure semantic-tone module tests (WO-P3-040, Layer-A).

No curses/terminal involved — asserts the palette table and the two
classifiers directly, per the ``tests/test_cockpit_hud.py`` /
``test_cockpit_goals.py`` / ``test_cockpit_focus.py`` /
``test_cockpit_decisions.py`` pure-function convention this mirrors.
"""

import math
from types import MappingProxyType

import pytest

from tw2002_aiclient.cockpit.tones import (
    STALE_RX_THRESHOLD_S,
    SEMANTIC_COLORS,
    gauge_semantic,
    status_semantic,
)

_ALL_TONES = {"ok", "warn", "danger"}


class HostileBool:
    def __bool__(self):
        raise RuntimeError("boom")


class HostileFloat:
    def __float__(self):
        raise RuntimeError("boom")


class HostileDict(dict):
    def __bool__(self):
        raise RuntimeError("boom")

    def get(self, key, default=None):
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# SEMANTIC_COLORS — table integrity, a literal pin against canon drift
# ---------------------------------------------------------------------------


def test_table_has_exactly_seven_keys():
    assert set(SEMANTIC_COLORS.keys()) == {
        "ok",
        "warn",
        "danger",
        "info",
        "gain",
        "loss",
        "muted",
    }


def test_table_values_pin_canon_fg_and_bold_exactly():
    # `canon/surfaces/visual-language.md` "Color semantics — the one
    # 7-tone table" — a literal pin so canon drift is caught immediately
    # rather than discovered visually.
    assert SEMANTIC_COLORS == {
        "ok": ("green", True),
        "warn": ("yellow", True),
        "danger": ("red", True),
        "info": ("cyan", False),
        "gain": ("green", True),
        "loss": ("red", True),
        "muted": ("default", False),
    }


def test_table_values_are_plain_tuples_of_str_and_bool():
    for tone, (color, bold) in SEMANTIC_COLORS.items():
        assert isinstance(color, str), tone
        assert isinstance(bold, bool), tone


def test_table_is_a_read_only_mapping_proxy_not_a_plain_dict():
    # SEMANTIC_COLORS is deliberately NOT a plain dict -- every curses-
    # facing consumer across the cockpit aliases this exact object, so a
    # writable dict would let a stray write through any one alias silently
    # corrupt the shared palette process-wide (Mack-flagged, WO-P3-040
    # REVISE). isinstance(dict) is intentionally False for a
    # MappingProxyType; equality against a dict literal still holds (see
    # test_table_values_pin_canon_fg_and_bold_exactly above).
    assert isinstance(SEMANTIC_COLORS, MappingProxyType)
    assert not isinstance(SEMANTIC_COLORS, dict)


def test_table_assignment_raises_type_error():
    with pytest.raises(TypeError):
        SEMANTIC_COLORS["ok"] = ("blue", False)


def test_table_item_deletion_raises_type_error():
    with pytest.raises(TypeError):
        del SEMANTIC_COLORS["ok"]


def test_table_pop_raises_attribute_error():
    # MappingProxyType exposes only the read-only Mapping surface -- it has
    # no `.pop`/`.update`/`.clear` at all, so a caller reaching for one of
    # those mutation methods fails immediately and loudly rather than
    # finding a working mutator.
    assert not hasattr(SEMANTIC_COLORS, "pop")
    assert not hasattr(SEMANTIC_COLORS, "update")
    assert not hasattr(SEMANTIC_COLORS, "clear")


# ---------------------------------------------------------------------------
# status_semantic — disconnected always wins
# ---------------------------------------------------------------------------


def test_disconnected_is_danger_regardless_of_age():
    assert status_semantic(False, 0.0) == "danger"
    assert status_semantic(False, None) == "danger"
    assert status_semantic(False, 9999.0) == "danger"


def test_connected_with_no_age_is_ok():
    assert status_semantic(True, None) == "ok"


# ---------------------------------------------------------------------------
# status_semantic — staleness boundary, inclusive on the stale side
# ---------------------------------------------------------------------------


def test_stale_boundary_just_under_threshold_is_ok():
    assert status_semantic(True, STALE_RX_THRESHOLD_S - 0.001) == "ok"


def test_stale_boundary_exactly_at_threshold_is_warn():
    assert status_semantic(True, STALE_RX_THRESHOLD_S) == "warn"


def test_stale_boundary_well_past_threshold_is_warn():
    assert status_semantic(True, STALE_RX_THRESHOLD_S + 100.0) == "warn"


def test_stale_threshold_value_is_five_seconds():
    assert STALE_RX_THRESHOLD_S == 5.0


def test_negative_age_clamps_to_zero_and_reads_ok():
    assert status_semantic(True, -50.0) == "ok"


# ---------------------------------------------------------------------------
# status_semantic — hostile-input hardening
# ---------------------------------------------------------------------------


def test_none_connected_is_danger():
    # None is cleanly falsy (no exception) -- a legitimate "not connected".
    assert status_semantic(None, 0.0) == "danger"


@pytest.mark.parametrize("hostile_connected", [HostileBool(), HostileDict(a=1)])
def test_raising_bool_dunder_connected_never_raises_and_degrades_to_warn(
    hostile_connected,
):
    # An object whose own truthiness genuinely cannot be evaluated (a
    # raising `__bool__`) is UNEVALUABLE, not cleanly falsy -- it degrades
    # to "warn" (attention without claiming an observed state), the same
    # principle gauge_semantic's own hostile-fraction handling uses. Landing
    # this on "danger" would be the false-alarm-honesty mistake
    # gauge_semantic explicitly rejects -- see `_safe_connected`'s and
    # `status_semantic`'s docstrings.
    assert status_semantic(hostile_connected, 0.0) == "warn"


@pytest.mark.parametrize("truthy_connected", [1, "yes", [1], {"a": 1}, "not-a-bool", object()])
def test_truthy_non_bool_connected_behaves_as_connected(truthy_connected):
    # Cleanly-truthy non-bool objects (no exception) are not "hostile" --
    # this classifier mirrors ordinary Python truthiness for whatever it's
    # handed, same as the archive's own bare `if not connected`.
    assert status_semantic(truthy_connected, None) == "ok"


@pytest.mark.parametrize("falsy_connected", [0, "", [], {}])
def test_falsy_non_bool_connected_behaves_as_disconnected(falsy_connected):
    assert status_semantic(falsy_connected, 0.0) == "danger"


@pytest.mark.parametrize(
    "bad_age",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
        "not-a-number",
        object(),
        HostileFloat(),
    ],
)
def test_hostile_age_never_raises_and_counts_as_not_stale(bad_age):
    # Mirrors hud.py's non-finite-age_s policy: an unknown age is "we
    # don't know how old this is", not "confidently very stale".
    assert status_semantic(True, bad_age) == "ok"


# ---------------------------------------------------------------------------
# gauge_semantic — threshold boundaries, inclusive on the named side
# ---------------------------------------------------------------------------


def test_gauge_full_is_ok():
    assert gauge_semantic(1.0) == "ok"


def test_gauge_empty_is_danger():
    assert gauge_semantic(0.0) == "danger"


def test_gauge_ok_boundary_exactly_at_half_is_ok():
    assert gauge_semantic(0.5) == "ok"


def test_gauge_just_under_half_is_warn():
    assert gauge_semantic(0.5 - 1e-9) == "warn"


def test_gauge_warn_boundary_exactly_at_point_two_is_warn():
    assert gauge_semantic(0.2) == "warn"


def test_gauge_just_under_point_two_is_danger():
    assert gauge_semantic(0.2 - 1e-9) == "danger"


def test_gauge_out_of_range_above_one_clamps_to_ok():
    assert gauge_semantic(1.5) == "ok"


def test_gauge_out_of_range_below_zero_clamps_to_danger():
    assert gauge_semantic(-0.3) == "danger"


# ---------------------------------------------------------------------------
# gauge_semantic — hostile-input hardening
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_fraction",
    [
        None,
        True,
        False,
        "not-a-number",
        float("nan"),
        object(),
        HostileFloat(),
        HostileDict(a=1),
    ],
)
def test_hostile_fraction_never_raises_and_degrades_to_warn(bad_fraction):
    # Pinned choice (see gauge_semantic's docstring): uncoercible input is
    # neither confidently "ok" nor confidently "danger" -- it's "warn",
    # the one tone whose own canon meaning is "attention-needed" rather
    # than a verdict in either direction. bool is deliberately included
    # here (excluded from numeric coercion, mirrors hud.py).
    assert gauge_semantic(bad_fraction) == "warn"


@pytest.mark.parametrize("bad_fraction", [float("inf"), float("-inf")])
def test_infinite_fraction_never_raises_and_degrades_to_warn(bad_fraction):
    assert gauge_semantic(bad_fraction) == "warn"


def test_nan_fraction_does_not_silently_fall_through_to_danger():
    # A bare `nan >= 0.5` / `nan >= 0.2` both evaluate False in Python, so
    # an unguarded ladder would silently misclassify NaN as "danger" --
    # this pins that the finiteness check intercepts it first.
    assert gauge_semantic(float("nan")) != "danger"
    assert gauge_semantic(float("nan")) == "warn"


def test_numeric_string_fraction_coerces_and_classifies():
    assert gauge_semantic("0.7") == "ok"
    assert gauge_semantic("0.1") == "danger"


# ---------------------------------------------------------------------------
# Both classifiers — "returns only ok|warn|danger" property sweep
# ---------------------------------------------------------------------------


_STATUS_SEMANTIC_SWEEP = [
    (True, 0.0),
    (True, None),
    (True, STALE_RX_THRESHOLD_S),
    (False, 0.0),
    (False, None),
    (None, None),
    ("garbage", "garbage"),
    (HostileBool(), HostileFloat()),
    (0, float("inf")),
    (1, float("-inf")),
    (object(), float("nan")),
]


@pytest.mark.parametrize("connected, age", _STATUS_SEMANTIC_SWEEP)
def test_status_semantic_always_returns_one_of_the_three_tones(connected, age):
    assert status_semantic(connected, age) in _ALL_TONES


_GAUGE_SEMANTIC_SWEEP = [
    0.0,
    0.2,
    0.5,
    1.0,
    1.5,
    -0.3,
    None,
    True,
    False,
    "0.4",
    "garbage",
    float("nan"),
    float("inf"),
    float("-inf"),
    object(),
    HostileFloat(),
    HostileDict(a=1),
]


@pytest.mark.parametrize("fraction", _GAUGE_SEMANTIC_SWEEP)
def test_gauge_semantic_always_returns_one_of_the_three_tones(fraction):
    assert gauge_semantic(fraction) in _ALL_TONES


def test_gauge_semantic_never_returns_a_non_finite_or_nan_lookalike():
    # Belt-and-suspenders: confirm the return value itself is one of the
    # three literal tone strings, not e.g. a stray float that happened to
    # stringify oddly.
    for fraction in _GAUGE_SEMANTIC_SWEEP:
        result = gauge_semantic(fraction)
        assert isinstance(result, str)
        assert result in {"ok", "warn", "danger"}
        assert not (isinstance(result, float) and math.isnan(result))
