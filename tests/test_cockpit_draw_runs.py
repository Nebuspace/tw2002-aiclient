"""``cockpit.draw.draw_runs`` -- per-run, sub-line curses attrs (WO-P4-053).

Wire-level addstr-recording tests only, mirroring
``tests/test_cockpit_viewport_paint.py``'s ``_RecordingWindow`` double
(``draw.py``'s ``_safe_write`` never calls ``addnstr``, per this project's
"curses test doubles are addstr-only" convention) and the fake-stdscr
attr-capture pattern this project's own memory notes point to for proving
per-cell/per-run curses attrs (pyte cannot see curses attrs at all).
"""

from __future__ import annotations

from tw2002_aiclient.cockpit.draw import draw_runs


class _RecordingWindow:
    def __init__(self, rows: int = 20, cols: int = 40) -> None:
        self._rows, self._cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))


# A 10-wide, 4-tall boxed region -> interior (y=1, x=1, w=8, h=2).
REGION = {"y": 0, "x": 0, "w": 10, "h": 4}


def _calls_at_row(win: _RecordingWindow, row_y: int) -> list[tuple[int, int, str, int]]:
    return [c for c in win.calls if c[0] == row_y]


# ---------------------------------------------------------------------------
# Exact per-run attr placement
# ---------------------------------------------------------------------------


def test_two_runs_paint_at_exact_offsets_with_own_attrs():
    win = _RecordingWindow()
    runs = [{"start": 0, "end": 3, "attr": 1}, {"start": 3, "end": 8, "attr": 2}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])

    calls = _calls_at_row(win, 1)
    # Base layer (uncolored) + two run overlays.
    assert (1, 1, "ABCDEFGH", 0) in calls
    assert (1, 1, "ABC", 1) in calls
    assert (1, 4, "DEFGH", 2) in calls


def test_single_run_shorter_than_line_leaves_rest_only_on_base_layer():
    win = _RecordingWindow()
    runs = [{"start": 2, "end": 5, "attr": 9}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])

    calls = _calls_at_row(win, 1)
    assert (1, 1, "ABCDEFGH", 0) in calls  # base layer: full text, uncolored
    assert (1, 3, "CDE", 9) in calls  # overlay: just the run's own span
    assert len(calls) == 2


def test_no_runs_only_draws_base_layer():
    win = _RecordingWindow()
    draw_runs(win, REGION, [("plain text", [])])
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "plain te", 0)]  # clipped to inner_w=8


def test_runs_none_only_draws_base_layer():
    win = _RecordingWindow()
    draw_runs(win, REGION, [("plain text", None)])
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "plain te", 0)]


# ---------------------------------------------------------------------------
# Runs straddling / past the interior's right edge
# ---------------------------------------------------------------------------


def test_run_straddling_right_edge_clips_cleanly():
    win = _RecordingWindow()
    # inner_w == 8; a run from cell 6 to 12 must truncate to cells [6, 8).
    runs = [{"start": 6, "end": 12, "attr": 5}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert (1, 7, "GH", 5) in calls
    # No overlay write ever reaches past the box's own interior budget.
    for _y, x, text, attr in calls:
        if attr == 5:
            assert x + len(text) <= 1 + 8


def test_run_entirely_past_right_edge_produces_no_overlay_write():
    win = _RecordingWindow()
    runs = [{"start": 10, "end": 15, "attr": 7}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]  # base layer only, no attr-7 write


def test_run_starting_negative_clips_to_left_edge():
    win = _RecordingWindow()
    runs = [{"start": -5, "end": 3, "attr": 4}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert (1, 1, "ABC", 4) in calls


# ---------------------------------------------------------------------------
# Wide-character (CJK, 2-cell) clipping -- never slice a wide glyph in half
# ---------------------------------------------------------------------------

WIDE_REGION = {"y": 0, "x": 0, "w": 12, "h": 4}  # interior w=10


def test_run_exactly_bounding_wide_char_includes_it_whole():
    win = _RecordingWindow()
    line = "A中B"  # A (1 cell) + 中 (2 cells) + B (1 cell)
    runs = [{"start": 1, "end": 3, "attr": 1}]  # exactly the wide char's span
    draw_runs(win, WIDE_REGION, [(line, runs)])
    calls = _calls_at_row(win, 1)
    assert (1, 2, "中", 1) in calls  # x = inner_x(1) + start(1)


def test_run_splitting_wide_char_mid_glyph_drops_it_rather_than_slicing():
    win = _RecordingWindow()
    line = "A中B"
    # [0, 2) only half-covers the wide char (cells 1-2) -- must be dropped
    # whole, never rendered as a mangled half-glyph.
    runs = [{"start": 0, "end": 2, "attr": 2}]
    draw_runs(win, WIDE_REGION, [(line, runs)])
    calls = _calls_at_row(win, 1)
    assert (1, 1, "A", 2) in calls
    assert not any(attr == 2 and "中" in text for _y, _x, text, attr in calls)


def test_run_starting_mid_wide_char_skips_it_and_keeps_trailing_char():
    win = _RecordingWindow()
    line = "A中B"
    # [2, 4) starts inside the wide char's own 2-cell span (cells 1-2) --
    # the wide char must be dropped whole; only the trailing "B" (cell 3)
    # survives.
    runs = [{"start": 2, "end": 4, "attr": 3}]
    draw_runs(win, WIDE_REGION, [(line, runs)])
    calls = _calls_at_row(win, 1)
    matches = [c for c in calls if c[3] == 3]
    assert matches == [(1, 4, "B", 3)]


# ---------------------------------------------------------------------------
# Malformed / hostile run entries -- degrade to the uncolored base layer
# ---------------------------------------------------------------------------


def test_non_dict_run_entries_are_dropped_without_crashing():
    win = _RecordingWindow()
    runs = ["garbage", 5, None, [1, 2], object()]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])  # must not raise
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]  # only the base layer wrote


def test_run_missing_start_or_end_is_dropped():
    win = _RecordingWindow()
    runs = [{"end": 3, "attr": 1}, {"start": 0, "attr": 2}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]


def test_run_missing_attr_defaults_to_zero_and_still_paints():
    win = _RecordingWindow()
    runs = [{"start": 0, "end": 3}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert (1, 1, "ABC", 0) in calls
    assert len(calls) == 2  # base layer + this overlay, distinct calls


def test_empty_span_run_is_dropped():
    win = _RecordingWindow()
    runs = [{"start": 4, "end": 4, "attr": 1}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]


def test_inverted_span_run_is_dropped():
    win = _RecordingWindow()
    runs = [{"start": 6, "end": 2, "attr": 1}]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]


def test_non_finite_numeric_run_fields_are_dropped_without_crashing():
    win = _RecordingWindow()
    runs = [
        {"start": float("nan"), "end": 5, "attr": 1},
        {"start": 0, "end": float("inf"), "attr": 2},
        {"start": 0, "end": 3, "attr": float("nan")},
    ]
    draw_runs(win, REGION, [("ABCDEFGH", runs)])  # must not raise
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]


def test_runs_field_itself_hostile_non_iterable_falls_back_to_base_layer():
    win = _RecordingWindow()
    draw_runs(win, REGION, [("ABCDEFGH", 5)])  # runs=5, not a list -- must not raise
    calls = _calls_at_row(win, 1)
    assert calls == [(1, 1, "ABCDEFGH", 0)]


def test_malformed_line_item_shape_is_skipped_entirely():
    win = _RecordingWindow()
    # h=5 -> inner_h=3, tall enough that all three list slots are reached
    # (REGION's own inner_h=2 would drop the third slot on height alone,
    # which would prove nothing about malformed-shape handling).
    tall_region = {"y": 0, "x": 0, "w": 10, "h": 5}
    draw_runs(
        win, tall_region, ["not-a-pair", (1, 2, 3), ("ABCDEFGH", [{"start": 0, "end": 2, "attr": 1}])]
    )
    # First two malformed items produce no calls at their row (1, 2); the
    # third, valid item still draws normally at row 3 (inner_y=1 + i=2).
    assert win.calls == [(3, 1, "ABCDEFGH", 0), (3, 1, "AB", 1)]


def test_non_str_text_line_is_skipped_without_crashing():
    win = _RecordingWindow()
    draw_runs(win, REGION, [(None, [{"start": 0, "end": 1, "attr": 1}])])  # must not raise
    assert _calls_at_row(win, 1) == []


# ---------------------------------------------------------------------------
# Control-character neutralization survives per-run overlay writes
# ---------------------------------------------------------------------------


def test_control_character_inside_a_run_span_is_neutralized():
    win = _RecordingWindow()
    line = "A\nBCDEFGH"  # embedded raw newline at index 1
    runs = [{"start": 0, "end": 3, "attr": 1}]
    draw_runs(win, REGION, [(line, runs)])
    calls = _calls_at_row(win, 1)
    # The overlay write for [0,3) covers "A", "\n", "B" -- the control
    # char must have been replaced with a space, never sent raw to addstr.
    overlay = [c for c in calls if c[3] == 1]
    assert overlay == [(1, 1, "A B", 1)]
    assert "\n" not in overlay[0][2]


def test_control_character_in_base_layer_is_also_neutralized():
    win = _RecordingWindow()
    line = "A\x07BCDEFG"
    draw_runs(win, REGION, [(line, [])])
    calls = _calls_at_row(win, 1)
    assert "\x07" not in calls[0][2]
    assert calls[0][2] == "A BCDEFG"


# ---------------------------------------------------------------------------
# Inset math / height truncation -- mirrors draw_lines_attrs
# ---------------------------------------------------------------------------


def test_boxed_false_uses_full_region_no_inset():
    win = _RecordingWindow()
    region = {"y": 2, "x": 3, "w": 6, "h": 2}
    draw_runs(win, region, [("abcdef", [{"start": 0, "end": 3, "attr": 1}])], boxed=False)
    calls = win.calls
    assert (2, 3, "abcdef", 0) in calls
    assert (2, 3, "abc", 1) in calls


def test_lines_beyond_interior_height_are_dropped():
    win = _RecordingWindow()
    # REGION's interior height is 2 -- a third line must be silently
    # dropped, same as draw_lines/draw_lines_attrs.
    draw_runs(win, REGION, [("row0", []), ("row1", []), ("row2", [])])
    rows_written = {y for y, _x, _t, _a in win.calls}
    assert rows_written == {1, 2}  # inner_y=1, inner_y+1=2 -- row2 never reached


def test_region_none_is_a_no_op():
    win = _RecordingWindow()
    draw_runs(win, None, [("text", [{"start": 0, "end": 1, "attr": 1}])])
    assert win.calls == []


def test_empty_lines_is_a_no_op():
    win = _RecordingWindow()
    draw_runs(win, REGION, [])
    assert win.calls == []


def test_multiple_lines_land_at_incrementing_rows():
    win = _RecordingWindow()
    draw_runs(win, REGION, [("row0", []), ("row1", [])])
    assert (1, 1, "row0", 0) in win.calls
    assert (2, 1, "row1", 0) in win.calls
