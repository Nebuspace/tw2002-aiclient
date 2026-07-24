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

_REGION_KEYS = ("strip", "left_gutter", "center", "right_gutter", "logs")


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

    left = regions["left_gutter"]
    assert left == {"y": 2, "x": 1, "w": 36, "h": 26}

    center = regions["center"]
    assert center == {"y": 2, "x": 39, "w": 82, "h": 26, "border": True}

    right = regions["right_gutter"]
    assert right == {"y": 2, "x": 123, "w": 36, "h": 26}

    logs = regions["logs"]
    assert logs == {"y": 36, "x": 1, "w": 158, "h": 3}

    # every region stays inside the outer frame's inner inset
    for region in (strip, left, center, right, logs):
        assert region["x"] >= 1
        assert region["y"] >= 1
        assert region["x"] + region["w"] <= 159
        assert region["y"] + region["h"] <= 39


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
