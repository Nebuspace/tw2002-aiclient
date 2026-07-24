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
    GOALS_BOX_MIN_H,
    HUD_BOX_MIN_H,
    LEFT_GUTTER_MIN_COLS,
    MIN_COLS,
    MIN_LINES,
    MINIMAL_HEADER_MIN_COLS,
    PRIORITIES_MIN_W,
    PRIORITIES_W,
    RIGHT_GUTTER_MIN_COLS,
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

    logs = regions["logs"]
    assert logs == {"y": 36, "x": 1, "w": 158, "h": 3}

    # every region stays inside the outer frame's inner inset
    for region in (strip, goals, left, center, right, decisions, logs):
        assert region["x"] >= 1
        assert region["y"] >= 1
        assert region["x"] + region["w"] <= 159
        assert region["y"] + region["h"] <= 39


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
