"""F4, pure half — ``menu_map_summary``/``format_menu_map_lines`` must be able
to say "unknown" without saying "off-map".

``cli.cmd_menumap`` is where the four failure-to-look paths are detected, but
the *rendering* they were collapsing into lives here, in the one composer of
the you-are-here line. Fixing it in the CLI by post-processing the returned
lines would have created a second composer of the same line, free to drift
from this one -- so the distinction is carried through the summary dict and
rendered at the single choke point.

Pure tests, no CLI, no daemon. The CLI wiring is proved separately in
tests/test_cli_menumap_lookup_honesty.py.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.menu.map_view import (
    format_menu_map_lines,
    format_menu_map_report,
    menu_map_summary,
    menu_map_summary_from_store,
)


def _node(sig, label=None):
    return {"signature": sig, "label": label}


def _edge(frm, key, to, kind="nav"):
    return {"from_node": frm, "key": key, "to_node": to, "kind": kind, "desc": None}


NODES = [_node("A", "Root"), _node("B", "Mid")]
EDGES = [_edge("A", "1", "B")]


# -- the default is unchanged ------------------------------------------------

def test_default_still_means_genuine_off_map():
    """No reason supplied -> the pre-existing claim, byte for byte. Every
    caller that has not been taught the distinction keeps its old behaviour,
    which is what makes this change safe to land under the live consumers."""
    s = menu_map_summary(NODES, EDGES, current_sig=None)

    assert s["current"] is None
    assert s["here_unknown"] is None
    assert format_menu_map_lines(s, cols=22)[1] == "here off-map"


def test_a_sig_that_is_not_in_the_map_is_still_off_map():
    """A signature that genuinely is not a known node: the lookup DID answer,
    it just answered "nowhere". Still entitled to the off-map claim."""
    s = menu_map_summary(NODES, EDGES, current_sig="not-a-real-sig")

    assert s["current"] is None
    assert s["here_unknown"] is None
    assert format_menu_map_lines(s, cols=22)[1] == "here off-map"


# -- the new state -----------------------------------------------------------

def test_a_reason_replaces_the_off_map_claim_with_canon_s_unknown_glyph():
    s = menu_map_summary(NODES, EDGES, current_sig=None, here_unknown="no daemon")
    line = format_menu_map_lines(s, cols=40)[1]

    assert line == "here ? no daemon"
    assert "off-map" not in line, "the claim must be replaced, not decorated"


def test_the_unknown_glyph_is_the_one_canon_names():
    """`?` is canon's unknown marker (visual-language.md:145) and has no ASCII
    twin, so this line degrades identically on a non-UTF-8 terminal -- unlike
    `★`, which the located line uses. Pinned so a later 'nicer glyph' edit has
    to argue with canon rather than with taste."""
    s = menu_map_summary(NODES, EDGES, here_unknown="screen is blank")
    line = format_menu_map_lines(s, cols=40)[1]

    assert line.startswith("here ? ")
    assert line.isascii(), line


def test_a_located_player_ignores_any_reason():
    """Belt and braces: a reason passed alongside a resolvable sig is
    meaningless, and must never produce a line claiming both."""
    s = menu_map_summary(NODES, EDGES, current_sig="A", here_unknown="no daemon")
    line = format_menu_map_lines(s, cols=40)[1]

    assert s["here_unknown"] is None, "cleared in the summary, not just at render"
    assert line == "here ★ Root"


@pytest.mark.parametrize("empty", [None, "", 0, False])
def test_falsy_reasons_mean_no_reason(empty):
    """`here_unknown=""` is not a reason; it must not render `here ? ` with a
    dangling nothing after the glyph."""
    s = menu_map_summary(NODES, EDGES, here_unknown=empty)

    assert s["here_unknown"] is None
    assert format_menu_map_lines(s, cols=40)[1] == "here off-map"


def test_a_non_string_reason_is_coerced_not_crashed():
    """The reason arrives from a caller; the composer coerces it the same way
    it already coerces `label`, rather than assuming a str."""
    s = menu_map_summary(NODES, EDGES, here_unknown=404)
    line = format_menu_map_lines(s, cols=40)[1]

    assert line == "here ? 404"


# -- clipping still holds ----------------------------------------------------

@pytest.mark.parametrize("cols", [8, 12, 22, 40, 80])
def test_the_unknown_line_still_obeys_the_column_budget(cols):
    """The cockpit renders this at cols=22; a long daemon error must clip like
    every other line rather than blow the panel."""
    s = menu_map_summary(
        NODES, EDGES,
        here_unknown="screen unavailable: " + ("x" * 200),
    )
    lines = format_menu_map_lines(s, cols=cols)

    assert all(len(line) <= cols for line in lines), lines


def test_no_summary_at_all_is_the_least_informed_state_not_a_position_claim():
    """Swept, not asked for: ``format_menu_map_lines(None)`` also said
    ``here off-map`` -- the most confident possible claim from the least
    informed possible state. No live caller reaches it (``tw menumap`` always
    builds a summary), so this pins a DORMANT branch; it is here because
    leaving the identical claim two lines from its fixed twin is how the
    defect grows back."""
    for falsy in (None, {}):
        lines = format_menu_map_lines(falsy, cols=40)
        assert lines[1] == "here ? no map", falsy
        assert "off-map" not in lines[1], falsy


def test_no_summary_at_all_claims_no_CONTENTS_either():
    """The report half of the branch directly above, deliberately left by the
    lane that fixed the ``format_menu_map_lines`` twin because it moves the
    report's line SHAPE, which was outside that order.

    ``format_menu_map_report`` appended ``dead-ends: (none)`` and
    ``orphans: (none)`` under the honest ``here ? no map``. ``(none)`` is a
    claim about CONTENTS, and with no summary there are no contents to have
    counted -- the operator could not tell "I looked and there were none"
    from "I could not look". Same dormancy as its twin: ``cmd_menumap``
    always builds a summary or returns 1 before printing, so this pins a
    DORMANT branch, not a live bug.

    The shape is ``loops.list_view.format_loops_report``'s, not a new one:
    that reader's falsy branch emits its unknown headline and then "**No
    empty line and no count**, because none was earned"
    (``loops/list_view.py:119-120``). So the lists are OMITTED -- not
    rendered empty, and not decorated with a fourth "unknown" phrasing that
    would only restate what ``here ? no map`` already said.
    """
    for falsy in (None, {}):
        report = format_menu_map_report(falsy)

        # The rule: with nothing established, the report adds NOTHING to the
        # header the lines composer already made honest.
        assert report == format_menu_map_lines(falsy, cols=80), falsy
        # Pinned literally too, so a reworded header cannot let both sides of
        # the assert above move together and keep this green.
        assert report == ["MAP —", "here ? no map"], falsy
        joined = "\n".join(report)
        for claim in ("(none)", "dead-ends:", "orphans:"):
            assert claim not in joined, (claim, falsy)


def test_a_genuinely_empty_map_still_earns_the_none_claim():
    """The other direction, and the one that keeps the fix above from being an
    over-correction: an empty store was READ, and a read that found nothing
    is entitled to say so. ``(none)`` stays exactly where it was earned."""
    s = menu_map_summary([], [])
    report = format_menu_map_report(s)
    joined = "\n".join(report)

    assert "dead-ends: (none)" in joined
    assert "orphans: (none)" in joined


def test_the_full_report_carries_the_reason_too():
    s = menu_map_summary(NODES, EDGES, here_unknown="lookup failed: ValueError")
    report = format_menu_map_report(s)

    assert report[1] == "here ? lookup failed: ValueError"
    assert "dead-ends: B" in "\n".join(report)


# -- the store wrapper passes it through --------------------------------------

def test_from_store_wrapper_passes_the_reason_through(tmp_path):
    from tw2002_aiclient.menu import knowledge

    path = tmp_path / "game_knowledge.json"
    knowledge.upsert_menu_node(path, "sig-a", label="Computer")

    s = menu_map_summary_from_store(path, here_unknown="no daemon")
    assert s["here_unknown"] == "no daemon"
    assert format_menu_map_lines(s, cols=40)[1] == "here ? no daemon"

    unchanged = menu_map_summary_from_store(path)
    assert unchanged["here_unknown"] is None
    assert format_menu_map_lines(unchanged, cols=40)[1] == "here off-map"
