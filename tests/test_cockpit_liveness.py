"""Pure liveness-cluster composer tests (WO-P3-038, Layer-A).

No curses/terminal involved — asserts the composed strings directly, per
the ``tests/test_cockpit_hud.py`` / ``test_cockpit_goals.py`` /
``test_cockpit_focus.py`` / ``test_cockpit_decisions.py`` pure-function
convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit.liveness import (
    HEARTBEAT_PERIOD_S,
    compose_liveness_cluster,
    format_tx_readout,
    heartbeat_glyph,
    spinner_glyph,
)

# ---------------------------------------------------------------------------
# heartbeat_glyph — phase boundaries
# ---------------------------------------------------------------------------


def test_heartbeat_period_is_point_eight():
    assert HEARTBEAT_PERIOD_S == 0.8


@pytest.mark.parametrize(
    "now,expected_unicode,expected_ascii",
    [
        (0.0, "●", "*"),
        (0.79, "●", "*"),
        (0.8, "○", "."),
        (1.59, "○", "."),
        (1.6, "●", "*"),
    ],
)
def test_heartbeat_phase_boundaries(now, expected_unicode, expected_ascii):
    assert heartbeat_glyph(now) == expected_unicode
    assert heartbeat_glyph(now, unicode_ok=False) == expected_ascii


def test_heartbeat_second_full_cycle_matches_first():
    # phase repeats every 2*HEARTBEAT_PERIOD_S == 1.6s. This asserts the
    # *formula's* own behavior (ported verbatim from the archive,
    # `int(now / HEARTBEAT_PERIOD_S) % 2`) using computed offsets (`t +
    # 1.6`) rather than independently-typed float literals -- a literal
    # like `2.4` is not the same float as `0.8 + 1.6` (IEEE-754 rounding:
    # `2.4 / 0.8 == 2.9999999999999996` truncates to phase 0, while
    # `(0.8 + 1.6) / 0.8 == 3.0000000000000004` truncates to phase 1), so
    # this compares each base against its own computed one-cycle-later
    # offset rather than a hand-picked literal that might land on the
    # wrong side of a rounding hair.
    assert heartbeat_glyph(0.0 + 1.6) == heartbeat_glyph(0.0)
    assert heartbeat_glyph(0.79 + 1.6) == heartbeat_glyph(0.79)
    assert heartbeat_glyph(0.8 + 1.6) == heartbeat_glyph(0.8)


# ---------------------------------------------------------------------------
# heartbeat_glyph — hardening
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [None, "not-a-number", object(), [], {}, float("inf"), float("-inf"), float("nan")],
)
def test_heartbeat_never_raises_on_hostile_now_and_reads_phase_zero(bad):
    assert heartbeat_glyph(bad) == "●"
    assert heartbeat_glyph(bad, unicode_ok=False) == "*"


def test_heartbeat_negative_now_clamps_to_phase_zero():
    assert heartbeat_glyph(-5.0) == "●"


def test_heartbeat_negative_now_just_past_boundary_still_clamps():
    # A negative value close to -0.8 would (unclamped) compute a nonzero
    # phase; clamping to 0.0 before the divide keeps this deterministic.
    assert heartbeat_glyph(-0.8) == "●"
    assert heartbeat_glyph(-1.6) == "●"


def test_heartbeat_raising_float_dunder_never_raises():
    class HostileFloat:
        def __float__(self):
            raise RuntimeError("boom")

    assert heartbeat_glyph(HostileFloat()) == "●"


def test_heartbeat_huge_int_never_raises():
    assert heartbeat_glyph(10**300) in ("●", "○")


def test_heartbeat_bool_input_coerces_like_a_number_not_raise():
    # bool is a legal float() input (True -> 1.0); this isn't the
    # sent_count numeric-guard concern (that's TX-specific), just a
    # never-raises check for an odd but coercible type.
    heartbeat_glyph(True)  # must not raise


# ---------------------------------------------------------------------------
# spinner_glyph — calm/None/invalid vs. valid int indexing
# ---------------------------------------------------------------------------


def test_spinner_none_is_calm_frame_zero():
    assert spinner_glyph(None) == "⠋"
    assert spinner_glyph(None, unicode_ok=False) == "|"


def test_spinner_default_arg_is_calm():
    assert spinner_glyph() == "⠋"


def test_spinner_valid_int_indexes_ramp():
    assert spinner_glyph(0) == "⠋"
    assert spinner_glyph(1) == "⠙"
    assert spinner_glyph(3) == "⠸"
    assert spinner_glyph(9) == "⠏"


def test_spinner_ascii_ramp_indexing():
    assert spinner_glyph(0, unicode_ok=False) == "|"
    assert spinner_glyph(1, unicode_ok=False) == "/"
    assert spinner_glyph(2, unicode_ok=False) == "-"
    assert spinner_glyph(3, unicode_ok=False) == "\\"


def test_spinner_int_wraps_modulo_ramp_length():
    assert spinner_glyph(10) == spinner_glyph(0)  # unicode ramp len 10
    assert spinner_glyph(13) == spinner_glyph(3)
    assert spinner_glyph(4, unicode_ok=False) == spinner_glyph(0, unicode_ok=False)  # ascii ramp len 4


def test_spinner_negative_int_is_a_valid_wrapped_index():
    # Python's % on a negative int yields a non-negative index -- a
    # negative frame is well-defined, not an error.
    assert spinner_glyph(-1) == "⠏"  # last unicode frame
    assert spinner_glyph(-1, unicode_ok=False) == "\\"  # last ascii frame


def test_spinner_huge_int_never_raises_and_indexes():
    assert spinner_glyph(10**100) in (
        "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏",
    )


@pytest.mark.parametrize("bad", ["3", 3.0, [], {}, object(), 3.5])
def test_spinner_non_int_frame_falls_back_to_calm(bad):
    assert spinner_glyph(bad) == "⠋"


@pytest.mark.parametrize("bad", [True, False])
def test_spinner_bool_frame_never_renders_as_a_number(bad):
    # bool is an int subclass in Python; True must not silently act as
    # frame 1 (or False as frame 0) -- both freeze calm instead.
    assert spinner_glyph(bad) == "⠋"


def test_spinner_hostile_mod_dunder_never_raises():
    class HostileInt(int):
        def __mod__(self, other):
            raise RuntimeError("boom")

    assert spinner_glyph(HostileInt(3)) == "⠋"


# ---------------------------------------------------------------------------
# format_tx_readout — idle vs sent vs malformed
# ---------------------------------------------------------------------------


def test_tx_status_none_is_idle():
    assert format_tx_readout(None) == "→ -"


def test_tx_status_missing_tx_key_is_idle():
    assert format_tx_readout({}) == "→ -"


def test_tx_status_tx_not_a_dict_is_idle():
    assert format_tx_readout({"tx": "nope"}) == "→ -"
    assert format_tx_readout({"tx": None}) == "→ -"
    assert format_tx_readout({"tx": []}) == "→ -"


def test_tx_sent_count_none_is_idle():
    assert format_tx_readout({"tx": {"sent_count": None}}) == "→ -"


def test_tx_sent_count_missing_key_is_idle():
    assert format_tx_readout({"tx": {}}) == "→ -"


def test_tx_sent_count_zero_is_idle_matches_archive_falsy_check():
    assert format_tx_readout({"tx": {"sent_count": 0}}) == "→ -"


def test_tx_sent_count_positive_int_renders():
    assert format_tx_readout({"tx": {"sent_count": 158}}) == "→ 158"


def test_tx_sent_count_whole_valued_float_renders_as_int():
    assert format_tx_readout({"tx": {"sent_count": 158.0}}) == "→ 158"


def test_tx_sent_count_fractional_float_is_idle():
    assert format_tx_readout({"tx": {"sent_count": 158.5}}) == "→ -"


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_tx_sent_count_non_finite_float_is_idle(bad):
    assert format_tx_readout({"tx": {"sent_count": bad}}) == "→ -"


def test_tx_sent_count_negative_is_idle():
    assert format_tx_readout({"tx": {"sent_count": -5}}) == "→ -"


@pytest.mark.parametrize("bad", [True, False])
def test_tx_sent_count_bool_never_renders_as_a_number(bad):
    # bool is an int subclass -- True must not read as "→ 1".
    assert format_tx_readout({"tx": {"sent_count": bad}}) == "→ -"


def test_tx_sent_count_string_is_idle_not_reparsed():
    assert format_tx_readout({"tx": {"sent_count": "158"}}) == "→ -"


def test_tx_sent_count_huge_int_never_raises_and_renders():
    huge = 10**50
    assert format_tx_readout({"tx": {"sent_count": huge}}) == f"→ {huge}"


def test_tx_extra_age_s_field_is_accepted_and_ignored():
    # age_s is part of the payload contract for forward-compat but not
    # consumed by this WO's rendering.
    assert format_tx_readout({"tx": {"sent_count": 42, "age_s": 3.5}}) == "→ 42"
    assert format_tx_readout({"tx": {"sent_count": 42, "age_s": float("nan")}}) == "→ 42"


@pytest.mark.parametrize("bad_status", [[], "nope", 42, object()])
def test_tx_non_dict_status_never_raises_and_is_idle(bad_status):
    assert format_tx_readout(bad_status) == "→ -"


def test_tx_hostile_dict_subclass_tx_slot_get_is_contained():
    class HostileDict(dict):
        def get(self, key, default=None):
            raise RuntimeError("boom")

    hostile = HostileDict()
    dict.__setitem__(hostile, "sent_count", 5)
    assert format_tx_readout({"tx": hostile}) == "→ -"


# ---------------------------------------------------------------------------
# format_tx_readout — the → glyph is NO-SWAP in both modes
# ---------------------------------------------------------------------------


def test_tx_arrow_glyph_never_swaps_when_idle():
    assert format_tx_readout(None, unicode_ok=True).startswith("→")
    assert format_tx_readout(None, unicode_ok=False).startswith("→")


def test_tx_arrow_glyph_never_swaps_when_sent():
    payload = {"tx": {"sent_count": 12}}
    assert format_tx_readout(payload, unicode_ok=True) == "→ 12"
    assert format_tx_readout(payload, unicode_ok=False) == "→ 12"


# ---------------------------------------------------------------------------
# compose_liveness_cluster — ordering, composition, width clip
# ---------------------------------------------------------------------------


def test_cluster_ordering_is_heartbeat_spinner_tx_space_separated():
    status = {"spinner_frame": 2, "tx": {"sent_count": 99}}
    line = compose_liveness_cluster(status, now=0.0, width=80)
    assert line == "● ⠹ → 99"


def test_cluster_ordering_stable_across_states():
    calm = compose_liveness_cluster(None, now=0.0, width=80)
    assert calm == "● ⠋ → -"
    busy = compose_liveness_cluster(
        {"spinner_frame": 5, "tx": {"sent_count": 7}}, now=0.8, width=80
    )
    assert busy == "○ ⠴ → 7"


def test_cluster_ascii_mode_arrow_never_swaps_while_glyphs_do():
    line = compose_liveness_cluster(
        {"spinner_frame": 1, "tx": {"sent_count": 3}}, now=0.0, width=80, unicode_ok=False
    )
    assert line == "* / → 3"


def test_cluster_none_status_degrades_every_field_independently():
    line = compose_liveness_cluster(None, now=1.6, width=80)
    # heartbeat still computes from now (phase 0 at 1.6s); spinner calm;
    # tx idle.
    assert line == "● ⠋ → -"


@pytest.mark.parametrize("bad_status", [[], "nope", 42, object()])
def test_cluster_hostile_status_never_raises(bad_status):
    line = compose_liveness_cluster(bad_status, now=0.0, width=80)
    assert line == "● ⠋ → -"


def test_cluster_width_clip_trims_line():
    status = {"spinner_frame": 0, "tx": {"sent_count": 158}}
    full = compose_liveness_cluster(status, now=0.0, width=80)
    clipped = compose_liveness_cluster(status, now=0.0, width=4)
    assert clipped == full[:4]
    assert len(clipped) == 4


def test_cluster_width_zero_or_negative_empties_line():
    status = {"spinner_frame": 0, "tx": {"sent_count": 158}}
    assert compose_liveness_cluster(status, now=0.0, width=0) == ""
    assert compose_liveness_cluster(status, now=0.0, width=-5) == ""


def test_cluster_width_non_int_never_raises_and_empties():
    status = {"spinner_frame": 0, "tx": {"sent_count": 158}}
    assert compose_liveness_cluster(status, now=0.0, width=None) == ""
    assert compose_liveness_cluster(status, now=0.0, width="wide") == ""


def test_cluster_width_overflow_error_never_raises_and_empties():
    # int(float("inf")) raises OverflowError, not TypeError/ValueError --
    # and json.loads happily decodes a bare `Infinity` literal to exactly
    # that float, so this is a realistic hostile-wire-payload shape.
    status = {"spinner_frame": 0, "tx": {"sent_count": 158}}
    assert compose_liveness_cluster(status, now=0.0, width=float("inf")) == ""


def test_cluster_hostile_now_never_raises():
    status = {"spinner_frame": 3, "tx": {"sent_count": 1}}
    line = compose_liveness_cluster(status, now=object(), width=80)
    assert line.startswith("●")  # hostile now -> phase 0 clamp


def test_cluster_spinner_frame_missing_key_is_calm():
    line = compose_liveness_cluster({"tx": {"sent_count": 1}}, now=0.0, width=80)
    assert line == "● ⠋ → 1"


def test_cluster_non_int_spinner_frame_is_calm():
    line = compose_liveness_cluster(
        {"spinner_frame": "not-an-int", "tx": {"sent_count": 1}}, now=0.0, width=80
    )
    assert line == "● ⠋ → 1"


# ---------------------------------------------------------------------------
# Never-raises sweep across every public function
# ---------------------------------------------------------------------------


_HOSTILE_INPUTS = [
    None,
    True,
    False,
    0,
    -1,
    3.5,
    float("inf"),
    float("-inf"),
    float("nan"),
    "",
    "text",
    [],
    {},
    object(),
]


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_heartbeat_glyph_never_raises_sweep(bad):
    heartbeat_glyph(bad)
    heartbeat_glyph(bad, unicode_ok=False)


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_spinner_glyph_never_raises_sweep(bad):
    spinner_glyph(bad)
    spinner_glyph(bad, unicode_ok=False)


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_format_tx_readout_never_raises_sweep(bad):
    format_tx_readout(bad)
    format_tx_readout(bad, unicode_ok=False)


@pytest.mark.parametrize("bad", _HOSTILE_INPUTS)
def test_compose_liveness_cluster_never_raises_sweep(bad):
    compose_liveness_cluster(bad, now=bad, width=bad)
    compose_liveness_cluster(bad, now=bad, width=bad, unicode_ok=False)
