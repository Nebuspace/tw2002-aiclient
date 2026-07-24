"""Trainer-cockpit frame geometry tests (PWO-031/033, Layer-A).

Pure functions, no curses/terminal involved — feeds ``frame_layout()``
synthetic ``(lines, cols)`` pairs and asserts the returned regions, per the
``tests/test_spectate_layout.py`` pure-function convention this ports
(archived: ``test_frame_layout_below_floor_is_too_small`` /
``..._right_gutter_tier_left_anchors_viewport`` /
``..._full_tier_centers_viewport_with_right_gutter``).
"""

import itertools

import pytest

from tw2002_aiclient.cockpit.layout import (
    FULL_GUTTER_MIN_COLS,
    GAME_H,
    GAME_W,
    GOALS_BOX_MIN_H,
    HUD_BOX_MIN_H,
    LEFT_GUTTER_MIN_COLS,
    LOGS_MIN_H,
    MIN_COLS,
    MIN_LINES,
    MINIMAL_HEADER_MIN_COLS,
    OUTER_FRAME_PAD,
    PRIORITIES_MIN_W,
    PRIORITIES_W,
    RIGHT_GUTTER_MIN_COLS,
    STRIP_H,
    VIEWPORT_H,
    VIEWPORT_W,
    frame_layout,
)

_REGION_KEYS = (
    "strip",
    "goals",
    "left_gutter",
    "center",
    "right_gutter",
    "decisions",
    "logs",
    "control_strip",
)


def _present_regions(regions):
    return [regions[k] for k in _REGION_KEYS if regions.get(k) is not None]


def _overlaps(a, b):
    """True if rectangles a/b (each {'y','x','w','h'}) share any cell."""
    a_x0, a_x1 = a["x"], a["x"] + a["w"]
    a_y0, a_y1 = a["y"], a["y"] + a["h"]
    b_x0, b_x1 = b["x"], b["x"] + b["w"]
    b_y0, b_y1 = b["y"], b["y"] + b["h"]
    return a_x0 < b_x1 and b_x0 < a_x1 and a_y0 < b_y1 and b_y0 < a_y1


# -- too_small -----------------------------------------------------------


def test_too_small_below_line_floor():
    regions = frame_layout(19, 200)
    assert regions["mode"] == "too_small"
    assert "19" in regions["message"] or "resize" in regions["message"].lower()
    for key in _REGION_KEYS:
        assert regions[key] is None
    assert regions["outer"] is None


def test_too_small_below_col_floor():
    regions = frame_layout(40, MIN_COLS - 1)
    assert regions["mode"] == "too_small"


def test_too_small_message_uses_the_times_glyph_not_ascii_x():
    """Canon-cited literal (visual-language.md:208, trainer-cockpit.md:368):
    ``Terminal too small (C×L) — need at least 60×20`` — the × glyph is a
    no-swap literal (same family as ·/—), never an ASCII "x" twin."""
    regions = frame_layout(19, 200)
    assert "×" in regions["message"]
    assert "x" not in regions["message"]
    assert f"{MIN_COLS}×{MIN_LINES}" in regions["message"]


def test_at_col_floor_is_not_too_small():
    regions = frame_layout(40, MIN_COLS)
    assert regions["mode"] != "too_small"
    assert regions["mode"] == "no_border"


def test_at_line_floor_is_not_too_small():
    regions = frame_layout(MIN_LINES, 200)
    assert regions["mode"] != "too_small"


# -- fold-ladder boundaries (each floor, at the boundary and boundary-1) --
#
# The 154/138/118/82 floors are INNER-cols floors (cols minus the 2-cell
# outer-frame inset) — hence feeding `frame_layout` a raw `cols` of
# `FLOOR + 2` to land exactly on the boundary, and `FLOOR + 1` to land one
# inner-col short of it. Only the too_small gate (MIN_COLS=60) is checked
# against raw `cols` directly (see the too_small tests above).


def test_full_tier_at_boundary_154():
    regions = frame_layout(40, FULL_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "full"
    assert regions["left_gutter"]["w"] == PRIORITIES_W


def test_drops_below_full_at_boundary_minus_one():
    regions = frame_layout(40, FULL_GUTTER_MIN_COLS + 1)
    assert regions["mode"] == "right_gutter"
    assert regions["left_gutter"]["w"] == PRIORITIES_MIN_W


def test_left_gutter_narrowed_at_boundary_138():
    regions = frame_layout(40, LEFT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    assert regions["left_gutter"]["w"] == PRIORITIES_MIN_W


def test_left_gutter_absent_below_boundary_138():
    regions = frame_layout(40, LEFT_GUTTER_MIN_COLS + 1)
    assert regions["mode"] == "right_gutter"
    assert regions["left_gutter"] is None


def test_right_gutter_present_at_boundary_118():
    regions = frame_layout(40, RIGHT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    assert regions["right_gutter"] is not None
    assert regions["left_gutter"] is None


def test_drops_to_minimal_below_boundary_118():
    regions = frame_layout(40, RIGHT_GUTTER_MIN_COLS + 1)
    assert regions["mode"] == "minimal"
    assert regions["right_gutter"] is None


def test_minimal_tier_at_boundary_82():
    regions = frame_layout(40, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["mode"] == "minimal"
    assert regions["center"]["border"] is True
    assert regions["center"]["w"] == VIEWPORT_W


def test_drops_to_no_border_below_boundary_82():
    regions = frame_layout(40, MINIMAL_HEADER_MIN_COLS + 1)
    assert regions["mode"] == "no_border"
    assert regions["center"]["border"] is False


# -- center viewport width contract --------------------------------------


def test_center_width_is_82_at_full_tier():
    regions = frame_layout(40, FULL_GUTTER_MIN_COLS + 2)
    assert regions["center"]["w"] == 82


def test_center_never_exceeds_viewport_width_across_bordered_tiers():
    for cols in (
        FULL_GUTTER_MIN_COLS + 2,
        LEFT_GUTTER_MIN_COLS + 2,
        RIGHT_GUTTER_MIN_COLS + 2,
        MINIMAL_HEADER_MIN_COLS + 2,
    ):
        regions = frame_layout(40, cols)
        assert regions["center"]["w"] == VIEWPORT_W


# -- PWO-051: GAME viewport content budget (placeholder-kill) -----------
#
# PREP §PWO-051's Accept: "geometry matches VIEWPORT_W/H / GAME_W/H" -- the
# GAME box's own INTERIOR content budget (one cell of border inset on every
# side, per ``visual-language.md``'s "Viewport zero-inset is an invariant")
# is exactly GAME_W x GAME_H whenever the center region has enough height to
# reach its own VIEWPORT_H ceiling; below that it clips per the SAME formula
# ``layout.py``'s own no_border branch uses (mirrored explicitly below,
# never a hand-typed literal -- ``STRIP_H``/``LOGS_MIN_H``/the CONTROL_STRIP
# carve are this module's own named constants, not magic numbers).


def test_game_content_budget_is_80x24_at_full_tier_with_ample_height():
    """At lines=40 the column band comfortably clears VIEWPORT_H (26) --
    see ``test_corner_and_edge_coords_at_40x160`` above, which already pins
    ``center['h'] == 26`` at this exact size -- so the GAME interior lands
    on its full GAME_W x GAME_H (80x24) budget, not a height-clipped one."""
    regions = frame_layout(40, FULL_GUTTER_MIN_COLS + 2)
    center = regions["center"]
    assert center["border"] is True
    assert center["h"] == VIEWPORT_H  # the ceiling never binds at this size
    assert center["w"] - 2 == GAME_W
    assert center["h"] - 2 == GAME_H


def test_game_content_budget_matches_across_every_bordered_tier():
    """Same 80x24 interior budget at every bordered tier, not just 'full'
    -- mirrors ``test_center_never_exceeds_viewport_width_across_bordered_
    tiers``'s own tier list, extended to the height side too."""
    for cols in (
        FULL_GUTTER_MIN_COLS + 2,
        LEFT_GUTTER_MIN_COLS + 2,
        RIGHT_GUTTER_MIN_COLS + 2,
        MINIMAL_HEADER_MIN_COLS + 2,
    ):
        regions = frame_layout(40, cols)
        center = regions["center"]
        assert center["border"] is True
        assert center["w"] - 2 == GAME_W
        assert center["h"] - 2 == GAME_H


def _expected_column_h(lines: int) -> int:
    """Mirrors ``frame_layout``'s own column-band height derivation
    (``STRIP_H``/``LOGS_MIN_H``/the CONTROL_STRIP carve, ``layout.py``
    lines ~175-222) -- computed here from the module's own named
    constants, never a hand-typed literal, so this stays correct if any of
    them ever change."""
    i_lines = lines - 2 * OUTER_FRAME_PAD
    rest_h = max(1, i_lines - STRIP_H)
    logs_h = min(LOGS_MIN_H, max(1, rest_h - 1))
    column_h = max(1, rest_h - logs_h)
    if column_h > 1:
        column_h -= 1  # CONTROL_STRIP's own single-row carve
    return column_h


def test_no_border_tier_center_dimensions_clip_to_layout_formula():
    """``no_border`` tier's own width/height ceiling formula (``layout.py``
    ~250-251: ``center_w = min(GAME_W, i_cols)``, ``center_h =
    min(GAME_H, column_h)``) -- re-derived here at two sizes, one where
    ``i_cols`` is the binding ceiling (narrow terminal) and one where
    ``column_h`` is (short terminal), so both halves of each ``min()`` are
    actually exercised rather than only ever hitting the same branch."""
    # Narrow (raw MIN_COLS floor -- i_cols=58 < GAME_W=80): width ceiling
    # binds on i_cols; height still has ample column_h (34, well above
    # GAME_H) so it ceilings on GAME_H itself.
    lines, cols = 40, MIN_COLS
    regions = frame_layout(lines, cols)
    assert regions["mode"] == "no_border"
    i_cols = cols - 2 * OUTER_FRAME_PAD
    assert i_cols < GAME_W  # confirms this size actually exercises the i_cols ceiling
    center = regions["center"]
    assert center["border"] is False
    assert center["w"] == min(GAME_W, i_cols)
    assert center["h"] == min(GAME_H, _expected_column_h(lines))

    # Short (the real MIN_LINES floor): column_h (13) is now the binding
    # height ceiling, below GAME_H (24).
    lines, cols = MIN_LINES, MIN_COLS
    regions = frame_layout(lines, cols)
    assert regions["mode"] == "no_border"
    expected_column_h = _expected_column_h(lines)
    assert expected_column_h < GAME_H  # confirms this size exercises the column_h ceiling
    center = regions["center"]
    assert center["border"] is False
    i_cols = cols - 2 * OUTER_FRAME_PAD
    assert center["w"] == min(GAME_W, i_cols)
    assert center["h"] == min(GAME_H, expected_column_h)


def test_minimal_tier_center_height_clips_to_layout_formula():
    """The ``minimal`` tier is still bordered (``center_h = min(VIEWPORT_H,
    column_h)`` -- the BORDERED half of the same formula, ``layout.py``
    line 251), so its own height ceiling is checked separately from the
    ``no_border`` cases above at the real MIN_LINES floor, where
    ``column_h`` (13) again binds below ``VIEWPORT_H`` (26)."""
    regions = frame_layout(MIN_LINES, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["mode"] == "minimal"
    center = regions["center"]
    assert center["border"] is True
    expected_column_h = _expected_column_h(MIN_LINES)
    assert expected_column_h < VIEWPORT_H
    assert center["h"] == min(VIEWPORT_H, expected_column_h)
    assert center["w"] == VIEWPORT_W


# -- corner/edge coords at a specific size (40 x 160, full tier) ---------


def test_corner_and_edge_coords_at_40x160():
    regions = frame_layout(40, 160)
    assert regions["mode"] == "full"

    outer = regions["outer"]
    assert outer == {"y": 0, "x": 0, "w": 160, "h": 40}

    strip = regions["strip"]
    assert strip == {"y": 1, "x": 1, "w": 158, "h": 1}

    # Left gutter is stacked GOALS (top, claims its own floor first) above
    # PRIORITIES (below, gets whatever height remains) as of PWO-034 —
    # together they still span the same y=2..28 / h=26 slot the single
    # PRIORITIES box occupied pre-PWO-034.
    goals = regions["goals"]
    assert goals == {"y": 2, "x": 1, "w": 36, "h": GOALS_BOX_MIN_H}

    left = regions["left_gutter"]
    assert left == {"y": 2 + GOALS_BOX_MIN_H, "x": 1, "w": 36, "h": 26 - GOALS_BOX_MIN_H}

    center = regions["center"]
    assert center == {"y": 2, "x": 39, "w": 82, "h": 26, "border": True}

    # Right gutter is stacked HUD (top, claims its own floor first) above
    # DECISIONS (below, gets whatever height remains) as of PWO-036 --
    # together they still span the same y=2..28 / h=26 slot the single
    # right_gutter box occupied pre-PWO-036. ``right_gutter`` keeps its key
    # as the HUD sub-region (unchanged from pre-036 draw code); ``decisions``
    # is the new sub-region below it.
    right = regions["right_gutter"]
    assert right == {"y": 2, "x": 123, "w": 36, "h": HUD_BOX_MIN_H}

    decisions = regions["decisions"]
    assert decisions == {
        "y": 2 + HUD_BOX_MIN_H,
        "x": 123,
        "w": 36,
        "h": 26 - HUD_BOX_MIN_H,
    }

    # LOGS shifts up by one row from its pre-CONTROL_STRIP position (y=36)
    # -- CONTROL_STRIP (WO-P3-038) now claims the frame's own last interior
    # row below it, carved out of the column band's slack, never out of
    # LOGS' own height (still exactly 3, its unchanged floor).
    logs = regions["logs"]
    assert logs == {"y": 35, "x": 1, "w": 158, "h": 3}

    control_strip = regions["control_strip"]
    assert control_strip == {"y": 38, "x": 1, "w": 158, "h": 1}

    # every region stays inside the outer frame's inner inset
    for region in (strip, goals, left, center, right, decisions, logs, control_strip):
        assert region["x"] >= 1
        assert region["y"] >= 1
        assert region["x"] + region["w"] <= 159
        assert region["y"] + region["h"] <= 39
    # CONTROL_STRIP is the true bottom-most interior row -- directly below
    # LOGS, no gap, and its own bottom edge sits exactly at the outer
    # frame's inner inset (row 39 is the outer frame's own bottom border).
    assert control_strip["y"] == logs["y"] + logs["h"]
    assert control_strip["y"] + control_strip["h"] == 39


# -- GOALS/PRIORITIES left-gutter stack (PWO-034) ------------------------


def test_goals_present_and_priorities_narrowed_at_right_gutter_tier():
    regions = frame_layout(40, LEFT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    goals, left = regions["goals"], regions["left_gutter"]
    assert goals is not None
    assert goals["w"] == PRIORITIES_MIN_W
    assert goals["h"] == GOALS_BOX_MIN_H
    assert left is not None
    assert left["w"] == PRIORITIES_MIN_W
    # PRIORITIES sits directly below GOALS, same x, no gap.
    assert left["y"] == goals["y"] + goals["h"]
    assert left["x"] == goals["x"]


def test_goals_absent_when_left_gutter_absent():
    regions = frame_layout(40, RIGHT_GUTTER_MIN_COLS + 2)
    assert regions["left_gutter"] is None
    assert regions["goals"] is None


def test_goals_claims_height_before_priorities_when_column_short(monkeypatch):
    """A center_h shorter than GOALS_BOX_MIN_H: GOALS still renders (takes
    the whole slot, clamped to what's available), PRIORITIES drops to
    ``None`` rather than the two panels overlapping or GOALS itself being
    starved below PRIORITIES. Unreachable under the real MIN_LINES=20 floor
    (column_h there is always >= 14 > GOALS_BOX_MIN_H=11), so this patches
    the constant to exercise the degrade branch directly -- same latent-guard
    shape as ``LOGS_MIN_H``'s own module comment."""
    import tw2002_aiclient.cockpit.layout as layout_module

    monkeypatch.setattr(layout_module, "GOALS_BOX_MIN_H", 999)
    regions = layout_module.frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    goals, left, center = regions["goals"], regions["left_gutter"], regions["center"]
    assert goals is not None
    assert goals["h"] == center["h"]  # clamped to the whole available slot
    assert left is None  # no height left for PRIORITIES


def test_goals_at_least_1x1_when_column_is_extremely_short(monkeypatch):
    """Even a pathologically short slot still yields a >=1x1 GOALS region,
    never a 0-height/absent one, matching the layout's 'clamped to at least
    1x1' invariant for every present region."""
    import tw2002_aiclient.cockpit.layout as layout_module

    monkeypatch.setattr(layout_module, "GOALS_BOX_MIN_H", 999)
    regions = layout_module.frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    assert regions["goals"]["h"] >= 1
    assert regions["goals"]["w"] >= 1


def test_goals_and_priorities_together_span_the_full_left_gutter_height():
    for cols in (FULL_GUTTER_MIN_COLS + 2, LEFT_GUTTER_MIN_COLS + 2):
        regions = frame_layout(40, cols)
        goals, left, center = regions["goals"], regions["left_gutter"], regions["center"]
        total_h = goals["h"] + (left["h"] if left is not None else 0)
        assert total_h == center["h"]


# -- HUD/DECISIONS right-gutter stack (PWO-036) ---------------------------


def test_hud_present_and_decisions_present_at_full_tier():
    regions = frame_layout(40, FULL_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "full"
    hud, decisions = regions["right_gutter"], regions["decisions"]
    assert hud is not None
    assert hud["h"] == HUD_BOX_MIN_H
    assert decisions is not None
    # DECISIONS sits directly below HUD, same x, no gap.
    assert decisions["y"] == hud["y"] + hud["h"]
    assert decisions["x"] == hud["x"]
    assert decisions["w"] == hud["w"]


def test_hud_present_and_decisions_present_at_narrowed_right_gutter_tier():
    regions = frame_layout(40, LEFT_GUTTER_MIN_COLS + 2)
    assert regions["mode"] == "right_gutter"
    hud, decisions = regions["right_gutter"], regions["decisions"]
    assert hud is not None
    assert hud["h"] == HUD_BOX_MIN_H
    assert decisions is not None
    assert decisions["y"] == hud["y"] + hud["h"]
    assert decisions["x"] == hud["x"]


def test_decisions_absent_when_right_gutter_absent():
    regions = frame_layout(40, MINIMAL_HEADER_MIN_COLS + 2)
    assert regions["right_gutter"] is None
    assert regions["decisions"] is None


def test_hud_claims_height_before_decisions_when_column_short(monkeypatch):
    """A center_h shorter than HUD_BOX_MIN_H: HUD still renders (takes the
    whole slot, clamped to what's available), DECISIONS drops to ``None``
    rather than the two panels overlapping or HUD itself being starved
    below DECISIONS. Unreachable under the real MIN_LINES=20 floor
    (column_h there is always >= 14 > HUD_BOX_MIN_H=12), so this patches
    the constant to exercise the degrade branch directly -- same
    monkeypatch shape as ``test_goals_claims_height_before_priorities_
    when_column_short``."""
    import tw2002_aiclient.cockpit.layout as layout_module

    monkeypatch.setattr(layout_module, "HUD_BOX_MIN_H", 999)
    regions = layout_module.frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    hud, decisions, center = regions["right_gutter"], regions["decisions"], regions["center"]
    assert hud is not None
    assert hud["h"] == center["h"]  # clamped to the whole available slot
    assert decisions is None  # no height left for DECISIONS


def test_hud_at_least_1x1_when_column_is_extremely_short(monkeypatch):
    """Even a pathologically short slot still yields a >=1x1 HUD region,
    never a 0-height/absent one, matching the layout's 'clamped to at least
    1x1' invariant for every present region."""
    import tw2002_aiclient.cockpit.layout as layout_module

    monkeypatch.setattr(layout_module, "HUD_BOX_MIN_H", 999)
    regions = layout_module.frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    assert regions["right_gutter"]["h"] >= 1
    assert regions["right_gutter"]["w"] >= 1


def test_hud_and_decisions_together_span_the_full_right_gutter_height():
    for cols in (FULL_GUTTER_MIN_COLS + 2, LEFT_GUTTER_MIN_COLS + 2, RIGHT_GUTTER_MIN_COLS + 2):
        regions = frame_layout(40, cols)
        hud, decisions, center = regions["right_gutter"], regions["decisions"], regions["center"]
        total_h = hud["h"] + (decisions["h"] if decisions is not None else 0)
        assert total_h == center["h"]


# -- CONTROL_STRIP bottom band (WO-P3-038) --------------------------------


def test_control_strip_present_and_below_logs_at_min_lines_floor():
    """At the real MIN_LINES=20 floor -- the smallest non-``too_small``
    height -- CONTROL_STRIP is present (its `column_h > 1` carve condition
    always holds here: rest_h=17, logs_h=LOGS_MIN_H=3, column_h=14 before
    the carve), full inner width, directly below LOGS, one row tall."""
    regions = frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    logs, control_strip = regions["logs"], regions["control_strip"]
    assert control_strip is not None
    assert control_strip["h"] == 1
    assert control_strip["w"] == logs["w"] == regions["strip"]["w"]
    assert control_strip["x"] == logs["x"]
    assert control_strip["y"] == logs["y"] + logs["h"]


def test_control_strip_present_at_no_border_tier():
    """Present/absent is deliberately decided by height alone, independent
    of the column's fold `mode` -- CONTROL_STRIP is a full-width band like
    `strip`/`logs`, not a gutter-tied instrument box, so it renders the same
    at the narrowest bordered-viewport-dropped tier too."""
    regions = frame_layout(MIN_LINES, MIN_COLS)
    assert regions["mode"] == "no_border"
    assert regions["control_strip"] is not None
    assert regions["control_strip"]["h"] == 1


def test_control_strip_never_shrinks_logs_below_its_own_floor(monkeypatch):
    """LOGS' own height must never shrink because of CONTROL_STRIP's
    addition -- proven directly by monkeypatching LOGS_MIN_H (mirroring the
    existing GOALS_BOX_MIN_H/HUD_BOX_MIN_H "claims height first" tests'
    monkeypatch shape) to a value the module itself would have to shrink to
    fit, and confirming LOGS still gets exactly that shrunk value, unchanged
    by CONTROL_STRIP's presence or absence."""
    import tw2002_aiclient.cockpit.layout as layout_module

    monkeypatch.setattr(layout_module, "LOGS_MIN_H", 10)
    regions = layout_module.frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    # rest_h=17, logs_h=min(10, max(1,16))=10 -- LOGS gets its full
    # (monkeypatched) floor regardless of what CONTROL_STRIP does next.
    assert regions["logs"]["h"] == 10


def test_control_strip_drops_first_when_column_has_no_slack(monkeypatch):
    """CONTROL_STRIP drops to ``None`` (never LOGS, never the column body
    below its own >=1-row floor) once LOGS' own floor consumes the column
    band down to exactly 1 row of slack. Monkeypatches LOGS_MIN_H large
    enough to hit that clamp at the real MIN_LINES floor -- same latent-
    guard-exercise shape as the sibling GOALS/HUD 'claims height first'
    tests -- unreachable at today's real LOGS_MIN_H=3."""
    import tw2002_aiclient.cockpit.layout as layout_module

    monkeypatch.setattr(layout_module, "LOGS_MIN_H", 999)
    regions = layout_module.frame_layout(MIN_LINES, FULL_GUTTER_MIN_COLS + 2)
    # rest_h=17, logs_h=min(999, max(1,16))=16, column_h=max(1,17-16)=1 --
    # column_h is not > 1, so CONTROL_STRIP's carve condition fails.
    assert regions["logs"]["h"] == 16
    assert regions["control_strip"] is None


def test_control_strip_absent_in_too_small_mode():
    regions = frame_layout(19, 200)
    assert regions["mode"] == "too_small"
    assert regions["control_strip"] is None


# -- non-overlap property sweep -------------------------------------------


def test_regions_never_overlap_across_a_size_sweep():
    line_values = (MIN_LINES, MIN_LINES + 1, 24, 30, 40, 80)
    col_values = (
        MIN_COLS,
        MIN_COLS + 1,
        MINIMAL_HEADER_MIN_COLS - 1,
        MINIMAL_HEADER_MIN_COLS,
        MINIMAL_HEADER_MIN_COLS + 1,
        RIGHT_GUTTER_MIN_COLS - 1,
        RIGHT_GUTTER_MIN_COLS,
        RIGHT_GUTTER_MIN_COLS + 1,
        LEFT_GUTTER_MIN_COLS - 1,
        LEFT_GUTTER_MIN_COLS,
        LEFT_GUTTER_MIN_COLS + 1,
        FULL_GUTTER_MIN_COLS - 1,
        FULL_GUTTER_MIN_COLS,
        FULL_GUTTER_MIN_COLS + 1,
        200,
    )
    for lines, cols in itertools.product(line_values, col_values):
        regions = frame_layout(lines, cols)
        if regions["mode"] == "too_small":
            continue
        present = _present_regions(regions)
        # every region clamps to at least 1x1
        for region in present:
            assert region["w"] >= 1, (lines, cols, region)
            assert region["h"] >= 1, (lines, cols, region)
        # every region stays inside the outer frame
        outer = regions["outer"]
        for region in present:
            assert region["x"] >= outer["x"], (lines, cols, region)
            assert region["y"] >= outer["y"], (lines, cols, region)
            assert region["x"] + region["w"] <= outer["x"] + outer["w"], (lines, cols, region)
            assert region["y"] + region["h"] <= outer["y"] + outer["h"], (lines, cols, region)
        # no two sibling regions share a cell
        for a, b in itertools.combinations(present, 2):
            assert not _overlaps(a, b), (lines, cols, a, b)


@pytest.mark.parametrize("lines,cols", [(MIN_LINES, MIN_COLS), (40, 300), (200, 400)])
def test_frame_layout_never_raises_across_extreme_sizes(lines, cols):
    regions = frame_layout(lines, cols)
    assert regions["mode"] in ("full", "right_gutter", "minimal", "no_border", "too_small")


# -- PWO-039: five-boundary fold-ladder re-proof sweep ---------------------
#
# The boundary tests above each pin one or two facts per floor (mode + one
# region's width, mostly). This sweep re-proves the SAME five floors --
# 154/138/118/82/60 -- each at the floor and one column short of it, as one
# full-fact matrix per boundary: mode, the presence/absence of every region
# the PWO-039 fold composer cares about (goals/left_gutter/right_gutter/
# decisions/control_strip), and the center viewport's x/w wherever that is
# cleanly derivable from this module's own named constants (never a bare
# re-typed magic number) -- new coverage the per-floor tests above don't
# already assert in one place (e.g. no existing test pins `decisions`
# presence/absence or center x specifically at the 118 or 60 floors).
#
# MIN_COLS=60 is the one floor of the five that is a RAW-cols gate, not an
# inner-cols one -- `frame_layout` compares `cols < MIN_COLS` directly (see
# its own too_small branch, and this file's "only the too_small gate is
# checked against raw cols directly" precedent in the module comments
# above) -- so unlike the other four floors, its "at floor"/"below floor"
# cases below use the raw MIN_COLS value itself rather than MIN_COLS+2/+1;
# using the same "+2" convention there would land 2 columns past the real
# too_small edge and prove nothing about it.


def test_pwo039_five_boundary_fold_ladder_sweep():
    lines = 40
    ox = OUTER_FRAME_PAD

    def _facts(regions):
        return {
            "mode": regions["mode"],
            "goals": regions["goals"] is not None,
            "left_gutter": regions["left_gutter"] is not None,
            "right_gutter": regions["right_gutter"] is not None,
            "decisions": regions["decisions"] is not None,
            "control_strip": regions["control_strip"] is not None,
        }

    # -- 154: FULL_GUTTER_MIN_COLS -- both gutters at full width -----------
    at = frame_layout(lines, FULL_GUTTER_MIN_COLS + 2)
    assert _facts(at) == {
        "mode": "full",
        "goals": True,
        "left_gutter": True,
        "right_gutter": True,
        "decisions": True,
        "control_strip": True,
    }
    # At exactly this floor, FULL_GUTTER_MIN_COLS == VIEWPORT_W + HUD_GUTTER_W
    # + PRIORITIES_W by construction (the constant's own definition), so the
    # "full" mode's centering math collapses to a left-anchor: center_x is
    # exactly the left gutter's own width past the outer inset.
    assert at["center"]["x"] == ox + PRIORITIES_W
    assert at["center"]["w"] == VIEWPORT_W
    assert at["center"]["border"] is True

    below = frame_layout(lines, FULL_GUTTER_MIN_COLS + 1)
    assert _facts(below) == {
        "mode": "right_gutter",
        "goals": True,
        "left_gutter": True,
        "right_gutter": True,
        "decisions": True,
        "control_strip": True,
    }
    assert below["center"]["x"] == ox + PRIORITIES_MIN_W
    assert below["center"]["w"] == VIEWPORT_W
    assert below["center"]["border"] is True

    # -- 138: LEFT_GUTTER_MIN_COLS -- narrowed left gutter still fits ------
    at = frame_layout(lines, LEFT_GUTTER_MIN_COLS + 2)
    assert _facts(at) == {
        "mode": "right_gutter",
        "goals": True,
        "left_gutter": True,
        "right_gutter": True,
        "decisions": True,
        "control_strip": True,
    }
    assert at["center"]["x"] == ox + PRIORITIES_MIN_W
    assert at["center"]["w"] == VIEWPORT_W

    below = frame_layout(lines, LEFT_GUTTER_MIN_COLS + 1)
    assert _facts(below) == {
        "mode": "right_gutter",
        "goals": False,
        "left_gutter": False,
        "right_gutter": True,
        "decisions": True,
        "control_strip": True,
    }
    assert below["center"]["x"] == ox
    assert below["center"]["w"] == VIEWPORT_W

    # -- 118: RIGHT_GUTTER_MIN_COLS -- viewport + right HUD only -----------
    at = frame_layout(lines, RIGHT_GUTTER_MIN_COLS + 2)
    assert _facts(at) == {
        "mode": "right_gutter",
        "goals": False,
        "left_gutter": False,
        "right_gutter": True,
        "decisions": True,
        "control_strip": True,
    }
    assert at["center"]["x"] == ox
    assert at["center"]["w"] == VIEWPORT_W

    below = frame_layout(lines, RIGHT_GUTTER_MIN_COLS + 1)
    assert _facts(below) == {
        "mode": "minimal",
        "goals": False,
        "left_gutter": False,
        "right_gutter": False,
        "decisions": False,
        "control_strip": True,
    }
    # Minimal tier is always bordered at VIEWPORT_W regardless of i_cols
    # (`center_w = VIEWPORT_W if border else ...`), centered within the
    # available inner width.
    assert below["center"]["w"] == VIEWPORT_W
    assert below["center"]["border"] is True

    # -- 82: MINIMAL_HEADER_MIN_COLS -- bordered viewport alone ------------
    at = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 2)
    assert _facts(at) == {
        "mode": "minimal",
        "goals": False,
        "left_gutter": False,
        "right_gutter": False,
        "decisions": False,
        "control_strip": True,
    }
    assert at["center"]["x"] == ox
    assert at["center"]["w"] == VIEWPORT_W
    assert at["center"]["border"] is True

    below = frame_layout(lines, MINIMAL_HEADER_MIN_COLS + 1)
    assert _facts(below) == {
        "mode": "no_border",
        "goals": False,
        "left_gutter": False,
        "right_gutter": False,
        "decisions": False,
        "control_strip": True,
    }
    assert below["center"]["x"] == ox
    assert below["center"]["border"] is False
    # no_border's own width formula: min(GAME_W, i_cols) -- i_cols here is
    # one short of the 82 floor, i.e. 81, which is still >= GAME_W (80), so
    # this lands on the GAME_W ceiling, not the i_cols term.
    assert below["center"]["w"] == GAME_W

    # -- 60: MIN_COLS -- a RAW-cols floor, not inner-cols (see note above) -
    at = frame_layout(lines, MIN_COLS)
    assert _facts(at) == {
        "mode": "no_border",
        "goals": False,
        "left_gutter": False,
        "right_gutter": False,
        "decisions": False,
        "control_strip": True,
    }
    assert at["center"]["x"] == ox
    assert at["center"]["border"] is False

    below = frame_layout(lines, MIN_COLS - 1)
    assert below["mode"] == "too_small"
    for key in ("goals", "left_gutter", "right_gutter", "decisions", "control_strip"):
        assert below[key] is None
