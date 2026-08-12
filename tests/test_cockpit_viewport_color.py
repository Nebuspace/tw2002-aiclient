"""Tests for the pure pyte-color-run -> curses-attr mapping (WO-P4-053
lane 1, ``tw2002_aiclient/cockpit/viewport_color.py``).

Pure-module tests only, mirroring ``tests/test_cockpit_viewport_paint.py``'s
own composer-test convention -- no real curses session for the ``run_attr``
tests below (they duck-type against a plain ``_FakePairs`` stand-in, no
``curses`` module patching needed at all).

WO-P4-053 draw-seam merge: this module's own ``GameCellPairs`` REFERENCE
allocator (a curses-facing ``(fg, bg) -> pair number`` cache) was folded
into ``screens.py``'s ``_SharedPairs`` and deleted here -- exactly ONE
process-lifetime allocator for the whole app (see that class's own
docstring for why a second one would reopen the Mack-flagged CRITICAL
pair-number-collision bug it exists to eliminate). The real allocation /
pair-exhaustion / cache-on-failure coverage that used to live in this file
now lives in ``tests/test_screens_shared_pairs.py``, alongside
``screens.py``'s existing chrome-color tests. What stays here is
``run_attr``'s own logic only: it is duck-typed against anything exposing
``attr_for(fg_name, bg_name) -> int`` and never imports or constructs a
real allocator itself.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient.cockpit import viewport_color as vc

# ---------------------------------------------------------------------------
# PYTE_TO_CURSES_COLOR -- exact name mapping (dict only; orphaned
# `_curses_color_of` wrapper retired — live resolution is pairs.attr_for)
# ---------------------------------------------------------------------------

# The exact pyte FG_ANSI/BG_ANSI vocabulary (session/terminal.py's own
# color_map() docstring), minus "default" which is deliberately absent from
# the dict (means terminal-default, resolved separately).
_PYTE_REAL_COLOR_NAMES = {"black", "red", "green", "brown", "blue", "magenta", "cyan", "white"}


def test_pyte_to_curses_color_covers_exactly_the_real_pyte_names():
    assert set(vc.PYTE_TO_CURSES_COLOR.keys()) == _PYTE_REAL_COLOR_NAMES


@pytest.mark.parametrize(
    "name,expected",
    [
        ("black", curses.COLOR_BLACK),
        ("red", curses.COLOR_RED),
        ("green", curses.COLOR_GREEN),
        ("brown", curses.COLOR_YELLOW),  # pyte's ANSI-yellow name quirk
        ("blue", curses.COLOR_BLUE),
        ("magenta", curses.COLOR_MAGENTA),
        ("cyan", curses.COLOR_CYAN),
        ("white", curses.COLOR_WHITE),
    ],
)
def test_pyte_to_curses_color_maps_every_real_pyte_name(name, expected):
    assert vc.PYTE_TO_CURSES_COLOR[name] == expected


def test_pyte_to_curses_color_default_and_unknown_absent():
    assert "default" not in vc.PYTE_TO_CURSES_COLOR
    assert vc.PYTE_TO_CURSES_COLOR.get("not-a-real-color", -1) == -1


# ---------------------------------------------------------------------------
# align_color_runs -- pure geometry
# ---------------------------------------------------------------------------


def _run(start, end, fg="red", bg="default", bold=False):
    return {"start": start, "end": end, "fg": fg, "bg": bg, "bold": bold}


def test_exact_run_survives_unchanged_when_fully_in_bounds():
    color_rows = [[_run(0, 5, fg="green")]]
    text_lines = ["hello"]
    assert vc.align_color_runs(color_rows, text_lines) == [
        [{"start": 0, "end": 5, "fg": "green", "bg": "default", "bold": False}]
    ]


def test_output_length_always_matches_text_lines_length():
    text_lines = ["a", "b", "c"]
    assert len(vc.align_color_runs(None, text_lines)) == 3
    assert len(vc.align_color_runs("garbage", text_lines)) == 3
    assert len(vc.align_color_runs([], text_lines)) == 3
    assert len(vc.align_color_runs([[], []], text_lines)) == 3  # too few color rows


def test_row_count_matches_color_rows_with_no_transform_needed():
    color_rows = [[_run(0, 3)], [_run(1, 4)]]
    text_lines = ["abc", "xyzz"]
    aligned = vc.align_color_runs(color_rows, text_lines)
    assert len(aligned) == 2
    assert aligned[0] == [{"start": 0, "end": 3, "fg": "red", "bg": "default", "bold": False}]
    assert aligned[1] == [{"start": 1, "end": 4, "fg": "red", "bg": "default", "bold": False}]


# --- top-drop transformation: bottom-anchored row alignment ---------------


def test_top_drop_alignment_bottom_anchors_surviving_color_rows():
    # 30 raw color rows, each tagged with its ORIGINAL row index via a
    # unique fg name -- mirrors test_cockpit_viewport_paint.py's own
    # row{i:02d} top-drop fixture. Only the LAST 25 survive in text_lines
    # (as compose_viewport_lines' own TOP-DROP would produce); the color
    # runs must align to those same 25 original rows (indices 5..29), never
    # the dropped rows 0..4.
    color_rows = [[_run(0, 3, fg=f"row{i:02d}")] for i in range(30)]
    text_lines = [f"row{i:02d}" for i in range(5, 30)]  # the surviving 25

    aligned = vc.align_color_runs(color_rows, text_lines)
    assert len(aligned) == 25
    # aligned[0] must carry row05's color tag (first survivor), not row00's.
    assert aligned[0][0]["fg"] == "row05"
    assert aligned[-1][0]["fg"] == "row29"
    tags = [row[0]["fg"] for row in aligned]
    assert tags == [f"row{i:02d}" for i in range(5, 30)]
    assert "row00" not in tags


def test_fewer_color_rows_than_text_lines_pads_leading_rows_uncolored():
    # Hostile/out-of-sync input: color_rows shorter than text_lines. The
    # missing LEADING rows degrade to [] rather than misaligning the ones
    # that do exist -- bottom-anchored, same direction as the top-drop.
    color_rows = [[_run(0, 2, fg="only-row")]]
    text_lines = ["aa", "bb", "cc"]
    aligned = vc.align_color_runs(color_rows, text_lines)
    assert aligned == [[], [], [{"start": 0, "end": 2, "fg": "only-row", "bg": "default", "bold": False}]]


# --- column clipping of runs straddling the width boundary ----------------


def test_run_straddling_the_clipped_width_boundary_truncates_not_drops():
    # Original row was wide; text_lines' row was already clipped to 40
    # chars. A run spanning 30..100 must survive, truncated to 30..40.
    color_rows = [[_run(30, 100, fg="cyan")]]
    text_lines = ["x" * 40]
    aligned = vc.align_color_runs(color_rows, text_lines)
    assert aligned == [[{"start": 30, "end": 40, "fg": "cyan", "bg": "default", "bold": False}]]


def test_run_entirely_beyond_the_clipped_width_is_dropped():
    color_rows = [[_run(50, 60)]]
    text_lines = ["x" * 40]
    assert vc.align_color_runs(color_rows, text_lines) == [[]]


def test_run_spanning_the_whole_original_row_clips_to_new_row_length():
    color_rows = [[_run(0, 100, fg="magenta")]]
    text_lines = ["y" * 12]
    assert vc.align_color_runs(color_rows, text_lines) == [
        [{"start": 0, "end": 12, "fg": "magenta", "bg": "default", "bold": False}]
    ]


def test_negative_start_clamps_to_zero_rather_than_dropping():
    color_rows = [[_run(-5, 5)]]
    text_lines = ["abcde"]
    assert vc.align_color_runs(color_rows, text_lines) == [
        [{"start": 0, "end": 5, "fg": "red", "bg": "default", "bold": False}]
    ]


# --- malformed-input family: degrade to uncolored, never raise ------------


def test_text_lines_not_a_list_or_tuple_is_empty():
    assert vc.align_color_runs([[_run(0, 1)]], None) == []
    assert vc.align_color_runs([[_run(0, 1)]], "nope") == []
    assert vc.align_color_runs([[_run(0, 1)]], 42) == []
    assert vc.align_color_runs([[_run(0, 1)]], {}) == []


def test_empty_text_lines_is_empty():
    assert vc.align_color_runs([[_run(0, 1)]], []) == []


def test_color_rows_row_not_a_list_degrades_only_that_row():
    color_rows = ["not-a-list", [_run(0, 2, fg="green")]]
    text_lines = ["aa", "bb"]
    assert vc.align_color_runs(color_rows, text_lines) == [
        [],
        [{"start": 0, "end": 2, "fg": "green", "bg": "default", "bold": False}],
    ]


def test_text_line_not_a_str_treats_row_as_zero_length():
    color_rows = [[_run(0, 5)]]
    text_lines = [42]
    assert vc.align_color_runs(color_rows, text_lines) == [[]]


@pytest.mark.parametrize(
    "bad_run",
    [
        {"start": 0, "end": 5, "fg": "red", "bg": "default"},  # missing bold
        {"end": 5, "fg": "red", "bg": "default", "bold": False},  # missing start
        {"start": 0, "fg": "red", "bg": "default", "bold": False},  # missing end
        {"start": 0, "end": 5, "bg": "default", "bold": False},  # missing fg
        {"start": 0, "end": 5, "fg": "red", "bold": False},  # missing bg
        {"start": "0", "end": 5, "fg": "red", "bg": "default", "bold": False},  # non-int start
        {"start": 0, "end": "5", "fg": "red", "bg": "default", "bold": False},  # non-int end
        {"start": True, "end": 5, "fg": "red", "bg": "default", "bold": False},  # bool start
        {"start": 0, "end": True, "fg": "red", "bg": "default", "bold": False},  # bool end
        {"start": 5, "end": 5, "fg": "red", "bg": "default", "bold": False},  # end == start
        {"start": 5, "end": 3, "fg": "red", "bg": "default", "bold": False},  # end < start
        {"start": 0, "end": 5, "fg": 7, "bg": "default", "bold": False},  # non-str fg
        {"start": 0, "end": 5, "fg": "red", "bg": None, "bold": False},  # non-str bg
        {"start": 0, "end": 5, "fg": "red", "bg": "default", "bold": "yes"},  # non-bool bold
        {"start": 0, "end": 5, "fg": "red", "bg": "default", "bold": 1},  # non-bool bold (int)
        "not-a-dict",
        None,
        42,
    ],
)
def test_malformed_run_shapes_drop_without_raising(bad_run):
    color_rows = [[bad_run]]
    text_lines = ["abcde"]
    assert vc.align_color_runs(color_rows, text_lines) == [[]]


def test_one_malformed_run_does_not_drop_sibling_valid_runs_in_the_same_row():
    color_rows = [[{"start": 0, "end": 2, "fg": "red"}, _run(2, 5, fg="green")]]
    text_lines = ["abcde"]
    assert vc.align_color_runs(color_rows, text_lines) == [
        [{"start": 2, "end": 5, "fg": "green", "bg": "default", "bold": False}]
    ]


# ---------------------------------------------------------------------------
# run_attr -- duck-typed against any (fg_name, bg_name) -> int allocator
# ---------------------------------------------------------------------------
#
# WO-P4-053 draw-seam merge: the pair-ALLOCATION logic this file used to
# test directly here (a reference ``GameCellPairs`` class) was absorbed into
# ``screens.py``'s ``_SharedPairs`` (widened to a ``(fg_name, bg_name)``
# cache key) rather than shipping as a second live allocator -- see that
# class's own docstring and ``viewport_color.run_attr``'s. Real
# allocation/pair-exhaustion coverage now belongs with ``_SharedPairs`` in
# ``screens.py``'s own test surface, not here. What THIS module still owns,
# and what these tests cover, is ``run_attr``'s own logic: it is duck-typed
# against anything exposing ``attr_for(fg_name, bg_name) -> int``, applies
# ``curses.A_BOLD`` on top only when a run's own ``"bold"`` is ``True``, and
# degrades a malformed run to ``curses.A_NORMAL`` without raising -- all
# independent of whatever the real allocator behind ``attr_for`` does.


class _FakePairs:
    """Minimal stand-in for the ``attr_for(fg_name, bg_name) -> int``
    protocol ``run_attr`` duck-types against (in production,
    ``screens.py``'s ``_shared_pairs``) -- records calls, returns a
    deterministic int per call so a test can tell exactly which
    ``(fg, bg)`` combo produced a given attr."""

    def __init__(self):
        self.calls: list[tuple[object, object]] = []

    def attr_for(self, fg_name, bg_name):
        self.calls.append((fg_name, bg_name))
        return 1


def test_run_attr_calls_attr_for_with_the_runs_fg_and_bg():
    pairs = _FakePairs()
    run = _run(0, 1, fg="red", bg="blue", bold=False)
    vc.run_attr(pairs, run)
    assert pairs.calls == [("red", "blue")]


def test_run_attr_ors_bold_only_when_true():
    pairs = _FakePairs()
    bold_run = _run(0, 1, fg="red", bg="default", bold=True)
    plain_run = _run(0, 1, fg="red", bg="default", bold=False)

    bold_attr = vc.run_attr(pairs, bold_run)
    plain_attr = vc.run_attr(pairs, plain_run)
    assert plain_attr == 1
    assert bold_attr == 1 | curses.A_BOLD
    assert plain_attr & curses.A_BOLD == 0
    assert bold_attr & curses.A_BOLD == curses.A_BOLD


def test_run_attr_hostile_bold_value_is_never_treated_as_true():
    pairs = _FakePairs()
    run = {"fg": "red", "bg": "default", "bold": 1}  # truthy int, not a real bool
    attr = vc.run_attr(pairs, run)
    assert attr & curses.A_BOLD == 0


def test_run_attr_non_dict_run_is_normal_and_never_calls_attr_for():
    pairs = _FakePairs()
    assert vc.run_attr(pairs, "nope") == curses.A_NORMAL
    assert vc.run_attr(pairs, None) == curses.A_NORMAL
    assert pairs.calls == []


def test_run_attr_missing_fg_bg_still_calls_attr_for_with_none_no_crash():
    # run_attr defends its own {"fg": str, "bg": str, "bold": bool} shape
    # only against a non-dict run (see the non-dict test above) -- a valid
    # but empty dict still reaches attr_for, with fg/bg passed through as
    # None. It's the ALLOCATOR's own job (a real _SharedPairs' _curses_
    # color_of-style hardening) to turn a hostile None into "default"; this
    # fake just proves run_attr doesn't crash or substitute a value itself.
    pairs = _FakePairs()
    assert vc.run_attr(pairs, {}) == 1  # _FakePairs.attr_for always returns 1
    assert pairs.calls == [(None, None)]
