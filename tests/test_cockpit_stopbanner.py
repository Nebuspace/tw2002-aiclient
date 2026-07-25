"""WO-P5-064 Layer-A -- the STOP banner composed from TYPED reason codes.

Canon: ``canon/architecture/control-and-escalation.md`` "Escalation
reason-code catalog" owns the enumerated catalog (the
``INTERVENTION_REASON_LABELS`` map + ``intervention_reason_label()``'s
open-by-construction pass-through); ``canon/surfaces/
mode-line-and-teach-controls.md`` "The STOP banner" + "The STOP /
escalation banner styling" own the three bands this composer emits.

The load-bearing property under test is HONESTY, not coverage: a banner
that invents a plausible-sounding reason for a code it does not know is
strictly worse than one that says nothing. So the catalog-coverage
matrix below is paired with the unknown-code and empty-code cases, and
with a cross-check that NO catalog label ever appears in the output for a
code that is not in the catalog.

Layer-B (the drawn banner, ``PlayShellScreen.draw()``'s wiring and the
region geometry it lands in) lives in
``tests/test_cockpit_stopbanner_wiring.py`` -- same split every sibling
cockpit panel uses (``test_cockpit_logsband.py`` /
``test_cockpit_logsband_pty.py``).
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import stopbanner


# ---------------------------------------------------------------------------
# The catalog itself -- canon/architecture/control-and-escalation.md's own
# table, transcribed here as an INDEPENDENT copy (not imported from the
# module under test, which would make every assertion below vacuous).
# ---------------------------------------------------------------------------

CANON_CATALOG = {
    "autopilot_halted": "autopilot halted",
    "autopilot_no_candidates": "autopilot no candidates",
    "explore_exhausted": "explore exhausted",
    "autopilot_max_ticks_exhausted": "autopilot max ticks exhausted",
    "autopilot_game_select": "autopilot game select",
    "human_attach_blocks_trainer": "human attach blocks trainer",
    "credits_unknown": "credits unknown",
    "credits_stale": "credits stale",
    "fighters_unknown": "fighters unknown",
    "fighters_stale": "fighters stale",
}

WIDE = 120


def _halt(*codes, mode=None, needs=True):
    """A daemon ``status`` payload carrying an escalation block, in the
    wire shape ``canon/architecture/control-and-escalation.md`` cites and
    the archive's own ``spectate_layout.compose_intervention_strip``
    consumes: ``status["intervention"] = {"needs_attention": bool,
    "reasons": [{"code": <code>}, ...]}``."""
    status = {"intervention": {"needs_attention": needs,
                               "reasons": [{"code": c} for c in codes]}}
    if mode is not None:
        status["mode"] = mode
    return status


# ---------------------------------------------------------------------------
# 1. Catalog coverage -- every canon code renders ITS canon label.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code,label", sorted(CANON_CATALOG.items()))
def test_every_canon_reason_code_renders_its_canon_label(code, label):
    lines = stopbanner.compose_stop_banner_lines(_halt(code), width=WIDE)
    assert lines, f"a halt carrying {code!r} must render a banner"
    assert lines[0] == f"! STOP — {label}"


def test_module_catalog_matches_canon_exactly_no_extra_no_missing():
    """The module's own map is the catalog, whole -- a code added to the
    module without a canon row (or a canon row dropped) fails here rather
    than silently widening/narrowing what the banner can claim."""
    assert dict(stopbanner.INTERVENTION_REASON_LABELS) == CANON_CATALOG


# ---------------------------------------------------------------------------
# 2. The honesty requirement -- an UNKNOWN code must not grow prose.
# ---------------------------------------------------------------------------


def test_unknown_code_passes_through_as_its_own_text_never_invented_prose():
    lines = stopbanner.compose_stop_banner_lines(
        _halt("quantum_flux_overload"), width=WIDE
    )
    assert lines[0] == "! STOP — quantum_flux_overload"


def test_unknown_code_never_borrows_any_catalog_label():
    """The sharp edge of the same rule: not merely "some text appears",
    but that NONE of the ten real labels leaks in as a guessed
    explanation for a code the catalog has never seen."""
    rendered = "\n".join(
        stopbanner.compose_stop_banner_lines(_halt("wormhole_collapse"), width=WIDE)
    )
    for label in CANON_CATALOG.values():
        assert label not in rendered, (
            f"unknown code borrowed the catalog label {label!r} -- invented prose"
        )


def test_empty_and_none_codes_render_the_canon_question_mark():
    """canon: "an empty code renders ``\"?\"`` -- the banner never invents
    a message and never blanks"."""
    for empty in ("", None):
        lines = stopbanner.compose_stop_banner_lines(_halt(empty), width=WIDE)
        assert lines[0] == "! STOP — ?"


def test_a_halt_with_no_reasons_at_all_still_states_the_halt_with_a_question_mark():
    """``needs_attention`` set but an empty ``reasons`` list: there IS no
    code, so the reason slot degrades to the same canon ``"?"`` rather
    than to a fabricated summary."""
    lines = stopbanner.compose_stop_banner_lines(_halt(), width=WIDE)
    assert lines[0] == "! STOP — ?"


def test_label_lookup_is_case_sensitive_and_does_not_fuzzy_match():
    """``AUTOPILOT_HALTED`` is a DIFFERENT code from ``autopilot_halted``;
    resolving it to the known label would be inventing a mapping canon
    does not have."""
    assert stopbanner.intervention_reason_label("AUTOPILOT_HALTED") == "AUTOPILOT_HALTED"
    assert stopbanner.intervention_reason_label("autopilot_halted ") == "autopilot_halted "


# ---------------------------------------------------------------------------
# 3. The needs_attention gate -- no halt, no banner.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        None,
        {},
        "not-a-dict",
        {"intervention": None},
        {"intervention": "not-a-dict"},
        {"intervention": {}},
        {"intervention": {"needs_attention": False,
                          "reasons": [{"code": "autopilot_halted"}]}},
        {"intervention": {"needs_attention": None,
                          "reasons": [{"code": "autopilot_halted"}]}},
    ],
)
def test_no_halt_renders_no_banner_at_all(status):
    assert stopbanner.needs_attention(status) is False
    assert stopbanner.compose_stop_banner_lines(status, width=WIDE) == []


def test_needs_attention_true_is_the_only_thing_that_raises_the_banner():
    assert stopbanner.needs_attention(_halt("autopilot_halted")) is True


# ---------------------------------------------------------------------------
# 4. Reason shapes -- dict entries, bare strings, several at once.
# ---------------------------------------------------------------------------


def test_bare_string_reasons_are_accepted_like_dict_reasons():
    status = {"intervention": {"needs_attention": True,
                               "reasons": ["credits_stale"]}}
    lines = stopbanner.compose_stop_banner_lines(status, width=WIDE)
    assert lines[0] == "! STOP — credits stale"


def test_several_reasons_are_joined_not_collapsed_to_the_first():
    lines = stopbanner.compose_stop_banner_lines(
        _halt("credits_unknown", "fighters_stale"), width=WIDE
    )
    assert lines[0] == "! STOP — credits unknown; fighters stale"


def test_a_non_list_reasons_field_degrades_to_the_question_mark_not_iterated():
    status = {"intervention": {"needs_attention": True, "reasons": "autopilot_halted"}}
    lines = stopbanner.compose_stop_banner_lines(status, width=WIDE)
    assert lines[0] == "! STOP — ?"


# ---------------------------------------------------------------------------
# 5. Band 2 -- the keyboard-handoff marker, claimed only when the wire
#    actually says the human holds the keyboard.
# ---------------------------------------------------------------------------


def test_handoff_band_reads_human_when_the_wire_says_human_holds_the_keyboard():
    lines = stopbanner.compose_stop_banner_lines(
        _halt("autopilot_halted", mode="human"), width=WIDE
    )
    assert lines[1] == "[ HUMAN — YOU HAVE CONTROL ]"
    assert lines[1] == stopbanner.HANDOFF_MARKER


@pytest.mark.parametrize("mode,expected", [("app", "[ APP ]"), ("spectate", "[ SPECTATE ]")])
def test_handoff_band_never_claims_human_while_another_holder_is_reported(mode, expected):
    lines = stopbanner.compose_stop_banner_lines(
        _halt("autopilot_halted", mode=mode), width=WIDE
    )
    assert lines[1] == expected
    assert "YOU HAVE CONTROL" not in lines[1]


@pytest.mark.parametrize("status_mode", [None, "", 17, [], {"a": 1}])
def test_handoff_band_degrades_to_question_mark_when_the_holder_is_unknown(status_mode):
    status = _halt("autopilot_halted")
    if status_mode is not None:
        status["mode"] = status_mode
    lines = stopbanner.compose_stop_banner_lines(status, width=WIDE)
    assert lines[1] == "[ ? ]"
    assert "YOU HAVE CONTROL" not in "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Band 3 -- the A/R/T teach affordances, labels only.
# ---------------------------------------------------------------------------


def test_teach_band_offers_the_three_moves_as_labels():
    lines = stopbanner.compose_stop_banner_lines(_halt("autopilot_halted"), width=WIDE)
    assert lines[2] == "teach:  A)nalyze  R)ecord  T)assign"
    assert lines[2] == stopbanner.TEACH_LINE


@pytest.mark.parametrize("token", ["A)nalyze", "R)ecord", "T)assign"])
def test_each_teach_affordance_is_visible_at_the_halt(token):
    lines = stopbanner.compose_stop_banner_lines(_halt("explore_exhausted"), width=WIDE)
    assert token in lines[2]


def test_teach_band_is_labels_only_and_never_claims_a_move_is_running():
    """PWO-066+ owns the wires. The banner must not imply any of the three
    has fired -- no progress/armed/running vocabulary on this line."""
    line = stopbanner.TEACH_LINE.lower()
    for banned in ("running", "armed", "analyzing", "recording", "playing", "firing"):
        assert banned not in line


# ---------------------------------------------------------------------------
# 7. Fit -- height folds from the BOTTOM so the reason line survives last.
# ---------------------------------------------------------------------------


def test_full_height_is_three_bands_in_canon_order():
    lines = stopbanner.compose_stop_banner_lines(
        _halt("autopilot_halted", mode="human"), width=WIDE
    )
    assert len(lines) == 3
    assert lines[0].startswith("! STOP")
    assert lines[1] == stopbanner.HANDOFF_MARKER
    assert lines[2] == stopbanner.TEACH_LINE
    assert stopbanner.BANNER_H == 3


@pytest.mark.parametrize("height,expected_count", [(0, 0), (1, 1), (2, 2), (3, 3), (9, 3)])
def test_height_folds_from_the_bottom_reason_line_survives_last(height, expected_count):
    lines = stopbanner.compose_stop_banner_lines(
        _halt("autopilot_halted", mode="human"), width=WIDE, height=height
    )
    assert len(lines) == expected_count
    if lines:
        assert lines[0].startswith("! STOP")


@pytest.mark.parametrize("height", [-1, 0])
def test_no_room_renders_nothing_rather_than_a_partial_glyph(height):
    assert stopbanner.compose_stop_banner_lines(
        _halt("autopilot_halted"), width=WIDE, height=height
    ) == []


# ---------------------------------------------------------------------------
# 8. Width -- clipped, never wrapped; the sibling-composer convention for
#    a non-positive width.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width", [1, 2, 5, 12, 27, 40, 80, 200])
def test_every_line_fits_the_given_width(width):
    lines = stopbanner.compose_stop_banner_lines(
        _halt("autopilot_max_ticks_exhausted", mode="human"), width=width
    )
    assert lines
    for line in lines:
        assert len(line) <= width


def test_non_positive_width_keeps_the_line_count_and_empties_each_line():
    """Mirrors ``goals.py``/``logsband.py``: a caller can always rely on
    the line COUNT reflecting real content presence, independent of
    whether width happens to be non-positive."""
    lines = stopbanner.compose_stop_banner_lines(_halt("autopilot_halted"), width=0)
    assert lines == ["", "", ""]


def test_a_narrow_banner_still_leads_with_the_attention_glyph():
    lines = stopbanner.compose_stop_banner_lines(_halt("autopilot_halted"), width=1)
    assert lines[0] == "!"


# ---------------------------------------------------------------------------
# 9. Hardening -- never raises, whatever the wire hands it.
# ---------------------------------------------------------------------------


class _Hostile:
    """Raises on every conversion a composer might reach for."""

    def __bool__(self):
        raise RuntimeError("hostile __bool__")

    def __str__(self):
        raise RuntimeError("hostile __str__")

    def __int__(self):
        raise RuntimeError("hostile __int__")


@pytest.mark.parametrize(
    "status",
    [
        {"intervention": {"needs_attention": True, "reasons": [{"code": _Hostile()}]}},
        {"intervention": {"needs_attention": True, "reasons": [_Hostile()]}},
        {"intervention": {"needs_attention": True, "reasons": [{"nope": 1}]}},
        {"intervention": {"needs_attention": True, "reasons": [None, "credits_stale"]}},
        {"intervention": {"needs_attention": True, "reasons": ({"code": "credits_stale"},)},
         "mode": _Hostile()},
        {"intervention": {"needs_attention": _Hostile()}},
    ],
)
def test_hostile_payloads_never_raise_and_never_blank_the_halt(status):
    lines = stopbanner.compose_stop_banner_lines(status, width=WIDE)
    # Either the gate honestly refused (no halt provable) or a banner
    # rendered -- but never an exception, and never a banner whose reason
    # slot silently vanished.
    if lines:
        assert lines[0].startswith("! STOP — ")
        assert lines[0] != "! STOP — "


@pytest.mark.parametrize("width", [None, "wide", float("inf"), float("nan"), _Hostile()])
def test_hostile_width_degrades_rather_than_raising(width):
    stopbanner.compose_stop_banner_lines(_halt("autopilot_halted"), width=width)


@pytest.mark.parametrize("height", [None, "three", float("inf"), _Hostile()])
def test_hostile_height_degrades_rather_than_raising(height):
    stopbanner.compose_stop_banner_lines(
        _halt("autopilot_halted"), width=WIDE, height=height
    )


def test_a_hostile_reason_entry_is_contained_and_its_siblings_still_render():
    """Per-item containment, the same shape ``goals.py``'s
    ``_safe_sector_token`` uses: one unrenderable entry must not void the
    other, real reasons in the same halt."""
    status = {"intervention": {"needs_attention": True,
                               "reasons": [_Hostile(), {"code": "credits_stale"}]}}
    lines = stopbanner.compose_stop_banner_lines(status, width=WIDE)
    assert "credits stale" in lines[0]
