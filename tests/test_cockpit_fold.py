"""Pure responsive-fold composer tests (WO-P3-039, Layer-A).

No curses/terminal involved — asserts the composed lines directly, per the
``tests/test_cockpit_decisions.py`` pure-function convention this mirrors.
"""

import pytest

from tw2002_aiclient.cockpit import autonomy_keys
from tw2002_aiclient.cockpit.decisions import (
    GLYPH_CHOSEN,
    GLYPH_OTHER,
    compose_decisions_lines,
)
from tw2002_aiclient.cockpit.fold import (
    FOCUS_LABEL,
    FORMATIONS_LABEL,
    GOALS_LABEL,
    compose_folded_decisions_lines,
)
from tw2002_aiclient.cockpit.formations import EMPTY_FORMATIONS, compose_formations_panel
from tw2002_aiclient.cockpit.goals import GLYPH_BLOCKED, GLYPH_MET, compose_goals_lines
from tw2002_aiclient.cockpit.focus import compose_focus_lines

# -- Fixtures ---------------------------------------------------------------
#
# Each fixture is deliberately real (non-empty) content in exactly one
# section's own field namespace, so trace-only/goals-only/focus-only tests
# can combine them freely. The trace fixture mirrors
# ``tests/test_cockpit_decisions.py``'s own 3-candidate fixture verbatim
# (three candidates, not four) so its composed length (3) never coincides
# with the calm-empty HELP marker's fixed length (4) -- a deliberate
# choice that keeps the width=0 "all-empty" comparison meaningful in tests
# below rather than accidentally colliding on line count alone.

_TRACE_STATUS = {
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

_GOALS_STATUS = {
    "turns_left": 12345,
    "credits": 987654,
    "stardock_sectors": [10, 42],
    "known_sectors": 30,
    "galaxy_size": 100,
    "formations_count": 3,
    "chain_hops": 5,
    "chain_unit": "hops",
    "ship_prices_count": 4,
    "hold_price_label": "1,200cr",
    "fighters_aboard": 10,
}

_FOCUS_STATUS = {
    "focus": {
        "candidates": [
            {"kind": "run_chain", "ev_per_turn": 12.5, "gated": False},
            {
                "kind": "upgrade",
                "ev_per_turn": None,
                "gated": True,
                "gate_reason": "path to StarDock unknown",
            },
        ]
    }
}

_FULL_STATUS = {**_TRACE_STATUS, **_GOALS_STATUS, **_FOCUS_STATUS}

# Exact combined shape for _FULL_STATUS at width=60 (3 trace + 1 GOALS label
# + 9 goals + 1 FOCUS label + 2 focus + 1 FORMATIONS label + 1 formations
# honest-empty = 18 lines) -- hand-computed from each sibling composer's own
# documented field mapping, pinned here as a single literal regression check
# covering order, labels, and glyph pass-through all at once (mirrors
# ``test_cockpit_decisions.py``'s own
# ``test_full_fixture_exact_lines_with_glyph_placement`` convention).
# _FULL_STATUS omits ``formations_panel`` (fixture pin, not a claim that
# world_stats lacks a producer — see ``test_world_stats.py``), so FORMATIONS
# renders its honest-empty line here.
_FULL_EXPECTED = [
    f"{GLYPH_CHOSEN} Trade chain +550.0cr/t loop @1<->3 margin 55/hold",
    f"{GLYPH_OTHER} Upgrade +200.0cr/t hold capacity +40",
    f"{GLYPH_BLOCKED} Explore turn-reserve<50",
    GOALS_LABEL,
    f"{GLYPH_MET} Turns 12,345",
    f"{GLYPH_MET} Credits 987,654",
    f"{GLYPH_MET} StarDock @10,42",
    "· Map 30/100 (30%)",
    "· Formations 3 found",
    f"{GLYPH_MET} Chain 5 hops",
    f"{GLYPH_MET} Ship prices 4 priced",
    f"{GLYPH_MET} Hold price 1,200cr",
    f"{GLYPH_MET} Fighters 10",
    FOCUS_LABEL,
    "1 Trade chain +12.5cr/t",
    f"2 {GLYPH_BLOCKED} Upgrade path to StarDock unknown",
    FORMATIONS_LABEL,
    EMPTY_FORMATIONS,
]

_UNKNOWN_GOALS_LINES = [
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


class _HostileDict(dict):
    """A ``dict`` subclass whose own ``.get`` raises -- the exact
    out-of-contract nested-payload hazard ``decisions.py``/``focus.py``
    document as "contained at the render layer instead of here". This
    module IS that render layer for the fold; each test below targets one
    specific nested slot to prove only that section drops."""

    def get(self, key, default=None):
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# All-empty collapse — never a stack of nothing but honest unknowns
# ---------------------------------------------------------------------------


def test_status_none_collapses_to_pane_empty():
    assert compose_folded_decisions_lines(None, width=60) == compose_decisions_lines(
        None, width=60
    )


def test_status_empty_dict_collapses_to_pane_empty():
    assert compose_folded_decisions_lines({}, width=60) == compose_decisions_lines(
        None, width=60
    )

def test_status_non_dict_types_never_raise_and_collapse():
    for bad in ("a string", 12345, 3.14, [1, 2, 3], object(), True):
        assert compose_folded_decisions_lines(bad, width=40) == compose_decisions_lines(
            None, width=40
        )


def test_all_three_sections_present_but_malformed_still_collapses():
    # autopilot_trace/focus keys present but empty-shaped, no GOALS fields
    # at all, and no formations_panel key in this fixture -- every section still
    # independently resolves to its own honest-empty marker, so the whole
    # pane still collapses.
    status = {"autopilot_trace": {}, "focus": {"candidates": []}}
    assert compose_folded_decisions_lines(status, width=60) == compose_decisions_lines(
        None, width=60
    )

# ---------------------------------------------------------------------------
# Full fixture — section order, labels, glyph pass-through, all in one pin
# ---------------------------------------------------------------------------


def test_full_fixture_section_order_labels_and_glyphs():
    assert compose_folded_decisions_lines(_FULL_STATUS, width=60) == _FULL_EXPECTED


def test_section_labels_are_bare_uppercase_no_glyph_no_colon():
    assert GOALS_LABEL == "GOALS"
    assert FOCUS_LABEL == "FOCUS"
    assert FORMATIONS_LABEL == "FORMATIONS"
    result = compose_folded_decisions_lines(_FULL_STATUS, width=60)
    assert result[3] == GOALS_LABEL  # right after the 3 trace lines
    assert result[13] == FOCUS_LABEL  # right after the 9 goals lines
    assert result[16] == FORMATIONS_LABEL  # right after the 2 focus lines


def test_no_ai_pilot_text_anywhere():
    result = compose_folded_decisions_lines(_FULL_STATUS, width=60)
    joined = " ".join(result).lower()
    assert "ai_pilot" not in joined
    assert "ai-pilot" not in joined


# ---------------------------------------------------------------------------
# One-section-live cases — the other two still render their honest-empty
# content in full (canon: "the operator keeps the status ... just
# relocated"), only ALL THREE together collapse.
# ---------------------------------------------------------------------------


def test_trace_only_others_honest_empty_still_render():
    result = compose_folded_decisions_lines(_TRACE_STATUS, width=60)
    assert result == (
        [
            f"{GLYPH_CHOSEN} Trade chain +550.0cr/t loop @1<->3 margin 55/hold",
            f"{GLYPH_OTHER} Upgrade +200.0cr/t hold capacity +40",
            f"{GLYPH_BLOCKED} Explore turn-reserve<50",
            GOALS_LABEL,
        ]
        + _UNKNOWN_GOALS_LINES
        + [FOCUS_LABEL, "—"]
        + [FORMATIONS_LABEL, EMPTY_FORMATIONS]
    )


def test_goals_only_others_honest_empty_still_render():
    # DECISIONS is no longer honest-empty for THIS fixture, and that is the
    # point of WO-STATUS-CHAIN-SCALARS-COACH rather than a regression: the
    # very `chain_hops`/`chain_unit` that render the GOALS "Chain 5 hops" row
    # are also the coach's `chain_opportunity` trigger, so a status rich
    # enough to show that row is by construction rich enough to teach from.
    # FOCUS (which this fixture says nothing about) is still honest-empty,
    # which is what keeps the "one section live, others still render" subject
    # of this test intact.
    result = compose_folded_decisions_lines(_GOALS_STATUS, width=60)
    assert result == (
        [
            "Celebrate longest profit chains",
            " Multi-hop adjacent station cycles where every hop margins p",
            " → Run find_profit_chains / longest_profit_chain on the grap",
            GOALS_LABEL,
        ]
        + [
            f"{GLYPH_MET} Turns 12,345",
            f"{GLYPH_MET} Credits 987,654",
            f"{GLYPH_MET} StarDock @10,42",
            "· Map 30/100 (30%)",
            "· Formations 3 found",
            f"{GLYPH_MET} Chain 5 hops",
            f"{GLYPH_MET} Ship prices 4 priced",
            f"{GLYPH_MET} Hold price 1,200cr",
            f"{GLYPH_MET} Fighters 10",
        ]
        + [FOCUS_LABEL, "—"]
        + [FORMATIONS_LABEL, EMPTY_FORMATIONS]
    )


def test_focus_only_others_honest_empty_still_render():
    result = compose_folded_decisions_lines(_FOCUS_STATUS, width=60)
    assert result == (
        list(autonomy_keys.compose_autonomy_help_lines())
        + [GOALS_LABEL]
        + _UNKNOWN_GOALS_LINES
        + [
            FOCUS_LABEL,
            "1 Trade chain +12.5cr/t",
            f"2 {GLYPH_BLOCKED} Upgrade path to StarDock unknown",
        ]
        + [FORMATIONS_LABEL, EMPTY_FORMATIONS]
    )


# ---------------------------------------------------------------------------
# Hostile per-section payloads — one section drops, its siblings survive
# ---------------------------------------------------------------------------


def test_hostile_autopilot_trace_payload_drops_trace_section_others_survive():
    status = {"autopilot_trace": _HostileDict(), **_GOALS_STATUS, **_FOCUS_STATUS}
    result = compose_folded_decisions_lines(status, width=60)
    # No trace lines and no leading honest-empty trace marker either -- the
    # section is fully absent (dropped), distinct from "still renders empty".
    assert result[0] == GOALS_LABEL
    assert result == (
        [GOALS_LABEL]
        + [
            f"{GLYPH_MET} Turns 12,345",
            f"{GLYPH_MET} Credits 987,654",
            f"{GLYPH_MET} StarDock @10,42",
            "· Map 30/100 (30%)",
            "· Formations 3 found",
            f"{GLYPH_MET} Chain 5 hops",
            f"{GLYPH_MET} Ship prices 4 priced",
            f"{GLYPH_MET} Hold price 1,200cr",
            f"{GLYPH_MET} Fighters 10",
        ]
        + [
            FOCUS_LABEL,
            "1 Trade chain +12.5cr/t",
            f"2 {GLYPH_BLOCKED} Upgrade path to StarDock unknown",
        ]
        + [FORMATIONS_LABEL, EMPTY_FORMATIONS]
    )


def test_hostile_focus_payload_drops_focus_section_others_survive():
    status = {"focus": _HostileDict(), **_TRACE_STATUS, **_GOALS_STATUS}
    result = compose_folded_decisions_lines(status, width=60)
    assert FOCUS_LABEL not in result
    assert result == (
        [
            f"{GLYPH_CHOSEN} Trade chain +550.0cr/t loop @1<->3 margin 55/hold",
            f"{GLYPH_OTHER} Upgrade +200.0cr/t hold capacity +40",
            f"{GLYPH_BLOCKED} Explore turn-reserve<50",
            GOALS_LABEL,
        ]
        + [
            f"{GLYPH_MET} Turns 12,345",
            f"{GLYPH_MET} Credits 987,654",
            f"{GLYPH_MET} StarDock @10,42",
            "· Map 30/100 (30%)",
            "· Formations 3 found",
            f"{GLYPH_MET} Chain 5 hops",
            f"{GLYPH_MET} Ship prices 4 priced",
            f"{GLYPH_MET} Hold price 1,200cr",
            f"{GLYPH_MET} Fighters 10",
        ]
        + [FORMATIONS_LABEL, EMPTY_FORMATIONS]
    )


def test_hostile_top_level_status_drops_all_sections_falls_back_to_pane_empty():
    # A hostile status shared by all three children (raising .get()) kills
    # every section at once -- the fold still falls back to the pane's own
    # honest-empty marker rather than ever returning [].
    result = compose_folded_decisions_lines(_HostileDict(), width=60)
    assert result == compose_decisions_lines(None, width=60)


# ---------------------------------------------------------------------------
# Width handling — clip sweep, hostile width, and the width<=0 GOALS quirk
# ---------------------------------------------------------------------------


def test_width_clip_sweep_every_line_within_budget():
    for width in (0, 1, 5, 8, 10, 16, 20, 26, 32, 40, 60, 80):
        lines = compose_folded_decisions_lines(_FULL_STATUS, width=width)
        for line in lines:
            assert len(line) <= max(width, 0)


def test_width_zero_or_negative_empties_every_line_keeping_shape():
    # _FULL_STATUS's 3-candidate trace never collides in length with the
    # fixed 2-line trace marker, so this stays the full 18-line stack (see
    # _FULL_EXPECTED), just every line clipped to "" -- not a false
    # all-empty collapse.
    for width in (0, -5):
        lines = compose_folded_decisions_lines(_FULL_STATUS, width=width)
        assert lines == [""] * len(_FULL_EXPECTED)


@pytest.mark.parametrize("bad_width", ["not-a-number", float("inf"), float("-inf"), float("nan")])
def test_hostile_width_never_raises(bad_width):
    lines = compose_folded_decisions_lines(_FULL_STATUS, width=bad_width)
    assert lines == [""] * len(_FULL_EXPECTED)


def test_width_zero_goals_only_status_collapses_due_to_fixed_line_count_quirk():
    """Documented quirk (module docstring): GOALS always returns exactly 9
    lines regardless of content, so at width<=0 its real (all-"") output is
    indistinguishable from its own empty marker (also all-"", same fixed
    length) purely by coincidence of shape -- a genuinely non-empty GOALS
    status collapses to the pane's calm-empty HELP marker at width 0 even
    though it would render in full at any real width (proven below at
    width=5, where "GOALS" -- exactly 5 characters -- survives unclipped)."""
    assert compose_folded_decisions_lines(_GOALS_STATUS, width=0) == (
        compose_decisions_lines(None, width=0)
    )

    result_wide = compose_folded_decisions_lines(_GOALS_STATUS, width=5)
    assert GOALS_LABEL in result_wide
    assert len(result_wide) > 2


# ---------------------------------------------------------------------------
# Reuse contract — this module never re-implements the child composers
# ---------------------------------------------------------------------------


def test_reuses_child_composers_verbatim_not_a_reimplementation():
    for status in (_FULL_STATUS, _TRACE_STATUS, _GOALS_STATUS, _FOCUS_STATUS, None):
        trace = compose_decisions_lines(status, width=60)
        goals = compose_goals_lines(status, width=60)
        focus = compose_focus_lines(status, width=60)
        formations = compose_formations_panel(status, width=60)
        result = compose_folded_decisions_lines(status, width=60)
        if (
            trace == compose_decisions_lines(None, width=60)
            and goals == compose_goals_lines(None, width=60)
            and focus == compose_focus_lines(None, width=60)
            and formations == compose_formations_panel(None, width=60)
        ):
            assert result == compose_decisions_lines(None, width=60)
        else:
            expected = (
                trace
                + [GOALS_LABEL]
                + goals
                + [FOCUS_LABEL]
                + focus
                + [FORMATIONS_LABEL]
                + formations
            )
            assert result == expected
