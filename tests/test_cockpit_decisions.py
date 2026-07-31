"""Pure DECISIONS-panel composer tests (PWO-036, Layer-A).

No curses/terminal involved — asserts the composed lines directly, per the
``tests/test_cockpit_focus.py`` pure-function convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit import autonomy_keys
from tw2002_aiclient.cockpit.decisions import (
    GLYPH_CHOSEN,
    GLYPH_OTHER,
    IMPERATIVE_DENYLIST,
    compose_decisions_lines,
)
from tw2002_aiclient.cockpit.focus import _KIND_LABELS
from tw2002_aiclient.cockpit.goals import GLYPH_BLOCKED, UNKNOWN_DETAIL

# Calm-empty = autonomy HELP one-liners (WO-WIRE-AUTONOMY-HELP-LINES).
# Width 80 fits every HELP line unclipped so Accept can assert full strings.
_EMPTY_WIDTH = 80
_EMPTY_LINES = list(autonomy_keys.compose_autonomy_help_lines())


def _empty_at(width: int) -> list[str]:
    if width <= 0:
        return [""] * len(_EMPTY_LINES)
    return [line[:width] for line in _EMPTY_LINES]

_FULL_TRACE_STATUS = {
    "autopilot_trace": {
        "chosen": "run_chain",
        "candidates": [
            {
                "kind": "run_chain",
                "ev_cr_per_turn": 550.0,
                "rationale": "loop @1<->3 margin 55/hold",
                "gated": False,
            },
            {
                "kind": "upgrade",
                "ev_cr_per_turn": 200.0,
                "rationale": "hold capacity +40",
                "gated": False,
            },
            {
                "kind": "explore",
                "ev_cr_per_turn": 10.0,
                "gated": True,
                "gate_reason": "turn-reserve<50",
            },
        ],
    }
}


# ---------------------------------------------------------------------------
# Empty / absent / malformed payload — two-line honest empty, never invented
# ---------------------------------------------------------------------------


def test_status_none_is_honest_empty():
    assert compose_decisions_lines(None, width=40) == _empty_at(40)


def test_status_empty_dict_is_honest_empty():
    assert compose_decisions_lines({}, width=40) == _empty_at(40)


def test_autopilot_trace_key_absent_is_honest_empty():
    assert compose_decisions_lines({"other": 1}, width=40) == _empty_at(40)


def test_autopilot_trace_non_dict_is_honest_empty():
    for bad in ("bogus", 5, [1, 2], object(), True):
        assert compose_decisions_lines({"autopilot_trace": bad}, width=40) == _empty_at(40)


def test_candidates_absent_is_honest_empty():
    assert compose_decisions_lines({"autopilot_trace": {}}, width=40) == _empty_at(40)


def test_candidates_empty_list_is_honest_empty():
    assert (
        compose_decisions_lines({"autopilot_trace": {"candidates": []}}, width=40)
        == _empty_at(40)
    )


def test_candidates_non_list_is_honest_empty():
    for bad in ("bogus", 5, {"a": 1}, object()):
        lines = compose_decisions_lines({"autopilot_trace": {"candidates": bad}}, width=40)
        assert lines == _empty_at(40)


def test_candidates_all_non_dict_entries_dropped_is_honest_empty():
    lines = compose_decisions_lines(
        {"autopilot_trace": {"candidates": ["bogus", 5, None, [1, 2]]}}, width=40
    )
    assert lines == _empty_at(40)


def test_status_non_dict_types_never_raise():
    for bad in ("a string", 12345, 3.14, [1, 2, 3], object(), True):
        assert compose_decisions_lines(bad, width=40) == _empty_at(40)


# ---------------------------------------------------------------------------
# Full fixture — exact lines, glyph placement, order preserved
# ---------------------------------------------------------------------------


def test_full_fixture_exact_lines_with_glyph_placement():
    lines = compose_decisions_lines(_FULL_TRACE_STATUS, width=60)
    assert lines == [
        f"{GLYPH_CHOSEN} Trade chain +550.0cr/t loop @1<->3 margin 55/hold",
        f"{GLYPH_OTHER} Upgrade +200.0cr/t hold capacity +40",
        f"{GLYPH_BLOCKED} Explore turn-reserve<50",
    ]


def test_order_is_never_resorted_by_this_module():
    # Deliberately worst-EV-first input — the composer must preserve the
    # trace's own order rather than re-sort by ev_cr_per_turn itself.
    status = {
        "autopilot_trace": {
            "chosen": "run_chain",
            "candidates": [
                {"kind": "explore", "ev_cr_per_turn": 10.0, "gated": False},
                {"kind": "run_chain", "ev_cr_per_turn": 550.0, "gated": False},
            ],
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines[0].startswith(f"{GLYPH_OTHER} Explore")
    assert lines[1].startswith(f"{GLYPH_CHOSEN} Trade chain")


def test_gated_wins_over_chosen_precedence():
    # A candidate the engine flagged gated is not actually pickable this
    # tick even when `chosen` names the same kind (bookkeeping artifact) —
    # the gated glyph must win.
    status = {
        "autopilot_trace": {
            "chosen": "upgrade",
            "candidates": [
                {"kind": "upgrade", "gated": True, "gate_reason": "no dock quote"},
            ],
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_BLOCKED} Upgrade no dock quote"]


def test_chosen_none_renders_all_non_gated_as_other():
    status = {
        "autopilot_trace": {
            "chosen": None,
            "candidates": [{"kind": "run_chain", "ev_cr_per_turn": 5.0, "gated": False}],
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Trade chain +5.0cr/t {UNKNOWN_DETAIL}"]
    assert not any(GLYPH_CHOSEN in ln for ln in lines)


def test_chosen_not_matching_any_candidate_marks_none_as_chosen():
    status = {
        "autopilot_trace": {
            "chosen": "hold_position",
            "candidates": [{"kind": "run_chain", "ev_cr_per_turn": 5.0, "gated": False}],
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Trade chain +5.0cr/t {UNKNOWN_DETAIL}"]


def test_non_str_chosen_never_raises_and_does_not_blank_the_panel():
    # Deliberate divergence from the archived stricter behavior (see module
    # docstring) — a malformed `chosen` degrades just that one comparison,
    # it does not blank an otherwise-valid candidate list.
    status = {
        "autopilot_trace": {
            "chosen": {"weird": "object"},
            "candidates": [{"kind": "run_chain", "ev_cr_per_turn": 1.0, "gated": False}],
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Trade chain +1.0cr/t {UNKNOWN_DETAIL}"]


# ---------------------------------------------------------------------------
# Per-field behavior
# ---------------------------------------------------------------------------


def test_gated_candidate_uses_blocked_glyph_and_reason():
    status = {
        "autopilot_trace": {
            "candidates": [
                {"kind": "upgrade", "gated": True, "gate_reason": "no dock quote"}
            ]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_BLOCKED} Upgrade no dock quote"]


def test_gated_candidate_missing_reason_falls_back_to_unknown_detail():
    status = {"autopilot_trace": {"candidates": [{"kind": "upgrade", "gated": True}]}}
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_BLOCKED} Upgrade {UNKNOWN_DETAIL}"]


def test_ungated_missing_ev_and_rationale_show_honest_unknown():
    status = {"autopilot_trace": {"candidates": [{"kind": "explore", "gated": False}]}}
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Explore ev {UNKNOWN_DETAIL} {UNKNOWN_DETAIL}"]


def test_missing_gated_key_defaults_to_ungated():
    status = {
        "autopilot_trace": {"candidates": [{"kind": "explore", "ev_cr_per_turn": 1.0}]}
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Explore +1.0cr/t {UNKNOWN_DETAIL}"]


def test_unrecognized_kind_is_humanized_not_dropped():
    status = {
        "autopilot_trace": {
            "candidates": [{"kind": "scout_frontier", "ev_cr_per_turn": 2.0, "gated": False}]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Scout Frontier +2.0cr/t {UNKNOWN_DETAIL}"]


def test_missing_kind_degrades_to_unknown_detail_label():
    status = {
        "autopilot_trace": {"candidates": [{"ev_cr_per_turn": 3.0, "gated": False}]}
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} {UNKNOWN_DETAIL} +3.0cr/t {UNKNOWN_DETAIL}"]


def test_negative_ev_renders_signed():
    status = {
        "autopilot_trace": {
            "candidates": [{"kind": "run_chain", "ev_cr_per_turn": -4.25, "gated": False}]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Trade chain -4.2cr/t {UNKNOWN_DETAIL}"]


def test_non_dict_candidate_entries_are_dropped_not_fabricated():
    status = {
        "autopilot_trace": {
            "candidates": [
                "bogus",
                {"kind": "run_chain", "ev_cr_per_turn": 1.0, "gated": False},
                None,
                {"kind": "explore", "ev_cr_per_turn": 2.0, "gated": False},
            ]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [
        f"{GLYPH_OTHER} Trade chain +1.0cr/t {UNKNOWN_DETAIL}",
        f"{GLYPH_OTHER} Explore +2.0cr/t {UNKNOWN_DETAIL}",
    ]


# ---------------------------------------------------------------------------
# Malformed / hostile values — never raises, always degrades
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_ev_never_raises_and_degrades_to_unknown(bad):
    status = {
        "autopilot_trace": {
            "candidates": [{"kind": "explore", "ev_cr_per_turn": bad, "gated": False}]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Explore ev {UNKNOWN_DETAIL} {UNKNOWN_DETAIL}"]


def test_non_numeric_ev_never_raises():
    status = {
        "autopilot_trace": {
            "candidates": [{"kind": "explore", "ev_cr_per_turn": "lots", "gated": False}]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Explore ev {UNKNOWN_DETAIL} {UNKNOWN_DETAIL}"]


def test_raising_str_on_kind_and_gate_reason_never_raises():
    class Boom:
        def __str__(self):
            raise RuntimeError("boom")

        __repr__ = __str__

    status = {
        "autopilot_trace": {
            "candidates": [{"kind": Boom(), "gated": True, "gate_reason": Boom()}]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_BLOCKED} {UNKNOWN_DETAIL} {UNKNOWN_DETAIL}"]


def test_raising_bool_on_gated_never_raises():
    class HostileBool:
        def __bool__(self):
            raise RuntimeError("boom")

    status = {
        "autopilot_trace": {
            "candidates": [
                {"kind": "explore", "ev_cr_per_turn": 1.0, "gated": HostileBool()}
            ]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    # A hostile __bool__ degrades to "not gated" rather than crashing.
    assert lines == [f"{GLYPH_OTHER} Explore +1.0cr/t {UNKNOWN_DETAIL}"]


def test_raising_float_on_ev_never_raises():
    class HostileFloat:
        def __float__(self):
            raise RuntimeError("boom")

    status = {
        "autopilot_trace": {
            "candidates": [
                {"kind": "explore", "ev_cr_per_turn": HostileFloat(), "gated": False}
            ]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [f"{GLYPH_OTHER} Explore ev {UNKNOWN_DETAIL} {UNKNOWN_DETAIL}"]


def test_control_chars_in_gate_reason_pass_through_safely():
    status = {
        "autopilot_trace": {
            "candidates": [
                {"kind": "upgrade", "gated": True, "gate_reason": "no dock\x07quote\n"}
            ]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    # _safe_str only strips leading/trailing whitespace; embedded control
    # bytes pass through untouched — this composer's contract is "never
    # raises", not "sanitizes control bytes" (the curses draw layer's job,
    # same boundary goals.py/focus.py draw for their own free-text fields).
    assert lines == [f"{GLYPH_BLOCKED} Upgrade no dock\x07quote"]


def test_dict_subclass_with_hostile_get_is_dropped():
    class HostileDict(dict):
        def get(self, key, default=None):
            raise RuntimeError("boom")

    status = {
        "autopilot_trace": {
            "candidates": [
                {"kind": "run_chain", "ev_cr_per_turn": 1.0, "gated": False},
                HostileDict(kind="upgrade"),
                {"kind": "explore", "ev_cr_per_turn": 3.0, "gated": False},
            ]
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines == [
        f"{GLYPH_OTHER} Trade chain +1.0cr/t {UNKNOWN_DETAIL}",
        f"{GLYPH_OTHER} Explore +3.0cr/t {UNKNOWN_DETAIL}",
    ]


def test_width_non_int_never_raises():
    lines = compose_decisions_lines(_FULL_TRACE_STATUS, width="not-a-number")
    assert lines == [""] * 3


# ---------------------------------------------------------------------------
# Width handling
# ---------------------------------------------------------------------------


def test_width_clip_sweep_every_line_within_budget():
    for width in (0, 1, 5, 8, 10, 16, 20, 26, 32, 40, 60, 80):
        lines = compose_decisions_lines(_FULL_TRACE_STATUS, width=width)
        assert len(lines) == 3
        for line in lines:
            assert len(line) <= width


def test_width_zero_or_negative_empties_every_line():
    assert compose_decisions_lines(_FULL_TRACE_STATUS, width=0) == [""] * 3
    assert compose_decisions_lines(_FULL_TRACE_STATUS, width=-5) == [""] * 3


def test_width_zero_on_empty_state_is_four_empty_lines():
    assert compose_decisions_lines(None, width=0) == _empty_at(0)


def test_empty_calm_shows_all_autonomy_help_lines() -> None:
    """WO-WIRE-AUTONOMY-HELP-LINES Accept: four HELP strings, H/O confirm-not-auto."""
    lines = compose_decisions_lines(None, width=_EMPTY_WIDTH)
    assert lines == _EMPTY_LINES
    assert autonomy_keys.EXPLORE_HELP in lines
    assert autonomy_keys.HOLD_HELP in lines
    assert autonomy_keys.OFFER_HELP in lines
    assert autonomy_keys.CHAINS_HELP in lines
    assert "confirm" in autonomy_keys.HOLD_HELP
    assert "not auto" in autonomy_keys.HOLD_HELP
    assert "confirm" in autonomy_keys.OFFER_HELP
    assert "not auto" in autonomy_keys.OFFER_HELP


# ---------------------------------------------------------------------------
# Phrasing pin — DECISIONS reads as reasoning, never a live command
# ---------------------------------------------------------------------------


def test_no_composed_line_begins_with_a_bare_word():
    # Structural guarantee: every non-empty DECISIONS line is glyph-prefixed
    # (canon ~388) — no line can begin with a verb, imperative or
    # otherwise, because the very first character is always ★/·/⊘.
    lines = compose_decisions_lines(_FULL_TRACE_STATUS, width=60)
    for line in lines:
        assert line[0] in {GLYPH_CHOSEN, GLYPH_OTHER, GLYPH_BLOCKED}


def test_fixed_vocabulary_never_uses_an_imperative_leading_word():
    # Belt-and-suspenders on the composer's OWN authored text (the fixed
    # kind-label map imported from focus.py, plus the two empty-state
    # strings) — not a general sanitizer for arbitrary wire text (see
    # module docstring's scope note and IMPERATIVE_DENYLIST's comment).
    candidate_phrases = set(_EMPTY_LINES) | set(_KIND_LABELS.values())
    for phrase in candidate_phrases:
        first_token = phrase.split()[0] if phrase.split() else phrase
        first_word = first_token.rstrip("…").lower()
        assert first_word not in IMPERATIVE_DENYLIST


# ---------------------------------------------------------------------------
# WO-COACH-LOOP-DEPLETING-TRIGGER — idle DECISIONS + intervention codes
# ---------------------------------------------------------------------------


@pytest.fixture
def _fresh_coach_kb():
    from tw2002_aiclient.cockpit import decisions as decisions_mod

    decisions_mod._reset_kb_cache_for_tests()
    yield
    decisions_mod._reset_kb_cache_for_tests()


@pytest.mark.parametrize("code", ["floor_reached", "turn_budget_exhausted"])
def test_depletion_intervention_renders_route_longevity_card(code, _fresh_coach_kb):
    status = {
        "intervention": {
            "needs_attention": True,
            "reasons": [{"code": code}],
        }
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines != _EMPTY_LINES
    joined = "\n".join(lines)
    assert "Rotate before decay" in joined or "remaining profitable" in joined


@pytest.mark.parametrize(
    "intervention",
    [
        None,
        {},
        {"needs_attention": True},
        {"needs_attention": True, "reasons": []},
        {"needs_attention": True, "reasons": [{"code": "near_miss"}]},
        {"needs_attention": True, "reasons": [{"code": "unknown_halt"}]},
        {"needs_attention": True, "reasons": ["floor_reached"]},  # not a dict
        {"needs_attention": True, "reasons": {"code": "floor_reached"}},
        {"needs_attention": True, "reasons": [{"code": 1}]},
    ],
)
def test_non_depletion_intervention_stays_honest_empty(intervention, _fresh_coach_kb):
    status = {} if intervention is None else {"intervention": intervention}
    assert compose_decisions_lines(status, width=60) == _empty_at(60)


def test_live_trace_still_wins_over_depletion_coach(_fresh_coach_kb):
    status = {
        **_FULL_TRACE_STATUS,
        "intervention": {
            "needs_attention": True,
            "reasons": [{"code": "floor_reached"}],
        },
    }
    lines = compose_decisions_lines(status, width=60)
    assert any("loop @1<->3" in ln for ln in lines)
    assert not any("Rotate before decay" in ln for ln in lines)


# ---------------------------------------------------------------------------
# WO-COACH-HAS-PORT — idle DECISIONS + status has_port merge
# ---------------------------------------------------------------------------


def test_has_port_true_renders_pair_trade_card(_fresh_coach_kb):
    lines = compose_decisions_lines({"has_port": True}, width=60)
    assert lines != _EMPTY_LINES
    joined = "\n".join(lines)
    assert "Pair trade loops" in joined


@pytest.mark.parametrize(
    "has_port",
    [False, 1, "yes", "True", None],
    ids=["false", "int-1", "yes", "str-True", "none"],
)
def test_has_port_non_identity_true_stays_honest_empty(has_port, _fresh_coach_kb):
    status = {"has_port": has_port} if has_port is not None else {"has_port": None}
    assert compose_decisions_lines(status, width=60) == _empty_at(60)


def test_live_trace_still_wins_over_has_port_coach(_fresh_coach_kb):
    status = {**_FULL_TRACE_STATUS, "has_port": True}
    lines = compose_decisions_lines(status, width=60)
    assert any("loop @1<->3" in ln for ln in lines)
    assert not any("Pair trade loops" in ln for ln in lines)


# ---------------------------------------------------------------------------
# WO-COACH-DEAD-END-COUNT — idle DECISIONS + status dead_end_count
# ---------------------------------------------------------------------------


def test_dead_end_count_positive_renders_hide_planet_card(_fresh_coach_kb):
    lines = compose_decisions_lines({"dead_end_count": 1}, width=60)
    assert lines != _EMPTY_LINES
    assert "Hide a planet in a dead-end" in "\n".join(lines)


@pytest.mark.parametrize(
    "dead_end_count",
    [0, -1, True, "1", 1.5, None],
    ids=["zero", "neg", "bool", "str", "float", "none"],
)
def test_dead_end_count_non_positive_int_stays_honest_empty(
    dead_end_count, _fresh_coach_kb
):
    status = (
        {"dead_end_count": dead_end_count}
        if dead_end_count is not None
        else {"dead_end_count": None}
    )
    assert compose_decisions_lines(status, width=60) == _empty_at(60)


def test_live_trace_still_wins_over_dead_end_coach(_fresh_coach_kb):
    status = {**_FULL_TRACE_STATUS, "dead_end_count": 3}
    lines = compose_decisions_lines(status, width=60)
    assert any("loop @1<->3" in ln for ln in lines)
    assert not any("Hide a planet in a dead-end" in ln for ln in lines)


# ---------------------------------------------------------------------------
# WO-STATUS-FIGHTERS-ABOARD — idle DECISIONS + status fighters_aboard
# ---------------------------------------------------------------------------


def test_fighters_aboard_zero_renders_shipyard_card(_fresh_coach_kb):
    lines = compose_decisions_lines({"fighters_aboard": 0}, width=60)
    assert lines != _EMPTY_LINES
    assert "Holds-first ship progression" in "\n".join(lines)


def test_fighters_aboard_absent_stays_honest_empty(_fresh_coach_kb):
    assert compose_decisions_lines({}, width=60) == _empty_at(60)


# ---------------------------------------------------------------------------
# WO-COACH-EXPLORE-MODE — idle DECISIONS + status explore_mode
# ---------------------------------------------------------------------------


def test_explore_mode_present_renders_exploring_frontier_card(_fresh_coach_kb):
    lines = compose_decisions_lines({"explore_mode": "map_fill"}, width=60)
    assert lines != _EMPTY_LINES
    assert "Density-scan before stepping" in "\n".join(lines)


@pytest.mark.parametrize(
    "explore_mode",
    ["off", "", "   ", None, 1, True],
    ids=["off", "empty", "blank", "none", "int", "bool"],
)
def test_explore_mode_off_or_hostile_stays_honest_empty(explore_mode, _fresh_coach_kb):
    status = (
        {"explore_mode": explore_mode}
        if explore_mode is not None
        else {"explore_mode": None}
    )
    assert compose_decisions_lines(status, width=60) == _empty_at(60)


def test_live_trace_still_wins_over_explore_mode_coach(_fresh_coach_kb):
    status = {**_FULL_TRACE_STATUS, "explore_mode": "map_fill"}
    lines = compose_decisions_lines(status, width=60)
    assert any("loop @1<->3" in ln for ln in lines)
    assert not any("Density-scan before stepping" in ln for ln in lines)

