"""Pure FOCUS-panel composer tests (PWO-035, Layer-A).

No curses/terminal involved — asserts the composed lines directly, per the
``tests/test_cockpit_goals.py`` pure-function convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit.focus import UNKNOWN_DETAIL, compose_focus_lines
from tw2002_aiclient.cockpit.goals import GLYPH_BLOCKED, compose_goals_lines

_FULL_FOCUS_STATUS = {
    "focus": {
        "candidates": [
            {"kind": "run_chain", "ev_per_turn": 12.5, "gated": False},
            {"kind": "explore", "ev_per_turn": 0.01, "gated": False},
            {
                "kind": "upgrade",
                "ev_per_turn": None,
                "gated": True,
                "gate_reason": "path to StarDock unknown",
            },
        ]
    }
}


# ---------------------------------------------------------------------------
# Empty / absent / malformed payload — honest empty, never invented
# ---------------------------------------------------------------------------


def test_status_none_is_honest_empty():
    assert compose_focus_lines(None, width=40) == ["—"]


def test_status_empty_dict_is_honest_empty():
    assert compose_focus_lines({}, width=40) == ["—"]


def test_focus_key_absent_is_honest_empty():
    assert compose_focus_lines({"other": 1}, width=40) == ["—"]


def test_focus_non_dict_is_honest_empty():
    for bad in ("bogus", 5, [1, 2], object(), True):
        assert compose_focus_lines({"focus": bad}, width=40) == ["—"]


def test_candidates_absent_is_honest_empty():
    assert compose_focus_lines({"focus": {}}, width=40) == ["—"]


def test_candidates_empty_list_is_honest_empty():
    assert compose_focus_lines({"focus": {"candidates": []}}, width=40) == ["—"]


def test_candidates_non_list_is_honest_empty():
    for bad in ("bogus", 5, {"a": 1}, object()):
        lines = compose_focus_lines({"focus": {"candidates": bad}}, width=40)
        assert lines == ["—"]


def test_candidates_all_non_dict_entries_dropped_is_honest_empty():
    lines = compose_focus_lines(
        {"focus": {"candidates": ["bogus", 5, None, [1, 2]]}}, width=40
    )
    assert lines == ["—"]


def test_status_non_dict_types_never_raise():
    for bad in ("a string", 12345, 3.14, [1, 2, 3], object(), True):
        assert compose_focus_lines(bad, width=40) == ["—"]


# ---------------------------------------------------------------------------
# Full fixture — exact lines, order preserved (never re-sorted)
# ---------------------------------------------------------------------------


def test_full_fixture_exact_lines_in_engine_order():
    lines = compose_focus_lines(_FULL_FOCUS_STATUS, width=40)
    assert lines == [
        "1 Trade chain +12.5cr/t",
        "2 Explore +0.0cr/t",
        f"3 {GLYPH_BLOCKED} Upgrade path to StarDock unknown",
    ]


def test_ranked_order_is_never_resorted_by_this_module():
    # Deliberately worst-EV-first input — the composer must preserve the
    # engine's own order rather than re-sort by ev_per_turn itself.
    status = {
        "focus": {
            "candidates": [
                {"kind": "explore", "ev_per_turn": 0.01, "gated": False},
                {"kind": "run_chain", "ev_per_turn": 99.0, "gated": False},
            ]
        }
    }
    lines = compose_focus_lines(status, width=40)
    assert lines[0].startswith("1 Explore")
    assert lines[1].startswith("2 Trade chain")


def test_focus_lines_differ_from_goals_lines_on_same_status():
    # The literal Accept criterion (PWO-035): FOCUS fixture lines != GOALS
    # lines composed from the same status dict.
    status = dict(_FULL_FOCUS_STATUS, turns_left=100, credits=5000)
    focus_lines = compose_focus_lines(status, width=40)
    goals_lines = compose_goals_lines(status, width=40)
    assert focus_lines != goals_lines
    assert not set(focus_lines) & set(goals_lines)


def test_no_focus_line_leads_with_a_goals_status_glyph():
    # Canon ~386: only ⊘ crosses over into FOCUS (as a gated marker, not a
    # leading status glyph) — ✓/·/? stay GOALS-only.
    lines = compose_focus_lines(_FULL_FOCUS_STATUS, width=40)
    for line in lines:
        assert line[0] not in {"✓", "·", "?"}


def test_no_chosen_marker_ever_rendered():
    # ★ is DECISIONS/autopilot-trace vocabulary (canon ~388), never FOCUS.
    lines = compose_focus_lines(_FULL_FOCUS_STATUS, width=40)
    assert not any("★" in line for line in lines)


# ---------------------------------------------------------------------------
# Per-field behavior
# ---------------------------------------------------------------------------


def test_gated_candidate_uses_blocked_glyph_and_reason():
    status = {
        "focus": {
            "candidates": [
                {"kind": "upgrade", "gated": True, "gate_reason": "no dock quote"}
            ]
        }
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 {GLYPH_BLOCKED} Upgrade no dock quote"]


def test_gated_candidate_missing_reason_falls_back_to_unknown_detail():
    status = {"focus": {"candidates": [{"kind": "upgrade", "gated": True}]}}
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 {GLYPH_BLOCKED} Upgrade {UNKNOWN_DETAIL}"]


def test_ungated_missing_ev_shows_honest_unknown_ev():
    status = {"focus": {"candidates": [{"kind": "explore", "gated": False}]}}
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 Explore ev {UNKNOWN_DETAIL}"]


def test_missing_gated_key_defaults_to_ungated():
    status = {"focus": {"candidates": [{"kind": "explore", "ev_per_turn": 1.0}]}}
    lines = compose_focus_lines(status, width=40)
    assert lines == ["1 Explore +1.0cr/t"]


def test_unrecognized_kind_is_humanized_not_dropped():
    status = {
        "focus": {"candidates": [{"kind": "scout_frontier", "ev_per_turn": 2.0}]}
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == ["1 Scout Frontier +2.0cr/t"]


def test_missing_kind_degrades_to_unknown_detail_label():
    status = {"focus": {"candidates": [{"ev_per_turn": 3.0, "gated": False}]}}
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 {UNKNOWN_DETAIL} +3.0cr/t"]


def test_negative_ev_renders_signed():
    status = {
        "focus": {"candidates": [{"kind": "run_chain", "ev_per_turn": -4.25}]}
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == ["1 Trade chain -4.2cr/t"]


def test_non_dict_candidate_entries_are_dropped_not_fabricated():
    status = {
        "focus": {
            "candidates": [
                "bogus",
                {"kind": "run_chain", "ev_per_turn": 1.0},
                None,
                {"kind": "explore", "ev_per_turn": 2.0},
            ]
        }
    }
    lines = compose_focus_lines(status, width=40)
    # Only the two real dict candidates survive, renumbered 1..2 — a
    # dropped garbage entry never consumes or breaks the rank sequence.
    assert lines == ["1 Trade chain +1.0cr/t", "2 Explore +2.0cr/t"]


# ---------------------------------------------------------------------------
# Malformed / hostile values — never raises, always degrades
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_ev_never_raises_and_degrades_to_unknown(bad):
    status = {"focus": {"candidates": [{"kind": "explore", "ev_per_turn": bad}]}}
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 Explore ev {UNKNOWN_DETAIL}"]


def test_non_numeric_ev_never_raises():
    status = {
        "focus": {"candidates": [{"kind": "explore", "ev_per_turn": "lots"}]}
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 Explore ev {UNKNOWN_DETAIL}"]


def test_raising_str_on_kind_and_gate_reason_never_raises():
    class Boom:
        def __str__(self):
            raise RuntimeError("boom")

        __repr__ = __str__

    status = {
        "focus": {
            "candidates": [
                {"kind": Boom(), "gated": True, "gate_reason": Boom()}
            ]
        }
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 {GLYPH_BLOCKED} {UNKNOWN_DETAIL} {UNKNOWN_DETAIL}"]


def test_raising_bool_on_gated_never_raises():
    class HostileBool:
        def __bool__(self):
            raise RuntimeError("boom")

    status = {
        "focus": {
            "candidates": [{"kind": "explore", "ev_per_turn": 1.0, "gated": HostileBool()}]
        }
    }
    lines = compose_focus_lines(status, width=40)
    # A hostile __bool__ degrades to "not gated" rather than crashing.
    assert lines == ["1 Explore +1.0cr/t"]


def test_raising_float_on_ev_per_turn_never_raises():
    # Mack's repro: float(value) calls value.__float__() for an arbitrary
    # object — a hostile __float__ raising something other than
    # TypeError/ValueError/OverflowError must still degrade to honest-
    # unknown EV, not escape the composer's "never raises" contract.
    class HostileFloat:
        def __float__(self):
            raise RuntimeError("boom")

    status = {
        "focus": {
            "candidates": [{"kind": "explore", "ev_per_turn": HostileFloat()}]
        }
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == [f"1 Explore ev {UNKNOWN_DETAIL}"]


def test_dict_subclass_with_hostile_get_is_dropped_and_survivors_renumber():
    # Mack's repro: isinstance(c, dict) alone doesn't stop a *real* dict
    # subclass whose own .get() raises — that candidate must be dropped
    # like any other malformed slot, and the surviving candidates still
    # renumber with no gap (same semantics as the non-dict-entry drop).
    class HostileDict(dict):
        def get(self, key, default=None):
            raise RuntimeError("boom")

    status = {
        "focus": {
            "candidates": [
                {"kind": "run_chain", "ev_per_turn": 1.0},
                HostileDict(kind="upgrade", ev_per_turn=2.0),
                {"kind": "explore", "ev_per_turn": 3.0},
            ]
        }
    }
    lines = compose_focus_lines(status, width=40)
    assert lines == ["1 Trade chain +1.0cr/t", "2 Explore +3.0cr/t"]


def test_width_non_int_never_raises():
    lines = compose_focus_lines(_FULL_FOCUS_STATUS, width="not-a-number")
    assert lines == [""] * 3


# ---------------------------------------------------------------------------
# Width handling
# ---------------------------------------------------------------------------


def test_width_clip_sweep_every_line_within_budget():
    for width in (0, 1, 5, 8, 10, 16, 20, 26, 32, 40, 80):
        lines = compose_focus_lines(_FULL_FOCUS_STATUS, width=width)
        assert len(lines) == 3
        for line in lines:
            assert len(line) <= width


def test_width_zero_or_negative_empties_every_line():
    assert compose_focus_lines(_FULL_FOCUS_STATUS, width=0) == [""] * 3
    assert compose_focus_lines(_FULL_FOCUS_STATUS, width=-5) == [""] * 3


def test_width_zero_on_empty_state_is_a_single_empty_line():
    assert compose_focus_lines(None, width=0) == [""]
