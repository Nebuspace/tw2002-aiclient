"""WO-P5-060 lane B -- App/Human control-strip mode-badge wiring.

Two halves:

  1. ``cockpit.draw.draw_segment_line`` clipping proofs -- the new segment-
     capable sibling of ``draw_lines_attrs``, self-contained (no dependency
     on the composer below). Wire-level addstr-recording tests, mirroring
     ``tests/test_cockpit_draw_runs.py``'s own ``_RecordingWindow`` double
     (``draw.py``'s ``_safe_write`` never calls ``addnstr``, per this
     project's "curses test doubles are addstr-only" convention).
  2. The screens-level wiring matrix -- driving ``PlayShellScreen.
     spectating``/``attached`` through a fake-stdscr attr capture (the
     WO-P3-037 idiom: pyte can't see curses attrs at all, so the fake
     window's own ``addstr`` call log is the only way to prove a chip's
     attr) against ``cockpit.control_seat.compose_control_strip_segments``
     (lane A's pinned contract).
"""

from __future__ import annotations

import curses

from tw2002_aiclient.cockpit.draw import draw_segment_line

# ---------------------------------------------------------------------------
# 1. draw_segment_line -- pure, wire-level addstr-recording proofs.
# ---------------------------------------------------------------------------


class _RecordingWindow:
    def __init__(self, rows: int = 20, cols: int = 40) -> None:
        self._rows, self._cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))


# A 10-wide, 4-tall boxed region -> interior (y=1, x=1, w=8, h=2).
BOXED_REGION = {"y": 0, "x": 0, "w": 10, "h": 4}
# An unboxed control-strip-shaped region -- no inset, matches how the real
# control_strip row is drawn (`boxed=False`, same as `draw_lines`'s existing
# strip/control_strip callers).
STRIP_REGION = {"y": 5, "x": 2, "w": 6, "h": 1}


def test_two_segments_paint_left_to_right_with_own_attrs():
    win = _RecordingWindow()
    draw_segment_line(win, BOXED_REGION, [("ABC", 1), ("DEFGH", 2)], boxed=True)
    assert win.calls == [(1, 1, "ABC", 1), (1, 4, "DEFGH", 2)]


def test_segment_straddling_budget_truncates_and_starves_the_next_segment():
    # inner_w=8: first segment ("ABCDEFGH", 6 cells) leaves 2 cells; second
    # segment ("XYZ", 3 cells) only 2 of which fit -> clipped to "XY";
    # nothing at all remains for a third segment.
    win = _RecordingWindow()
    draw_segment_line(
        win, BOXED_REGION, [("ABCDEF", 1), ("XYZ", 2), ("QQQQ", 3)], boxed=True
    )
    assert win.calls == [(1, 1, "ABCDEF", 1), (1, 7, "XY", 2)]


def test_wide_char_straddling_the_boundary_drops_whole_not_split():
    # inner_w=8. First segment consumes 7 cells, leaving exactly 1 -- a
    # 2-cell CJK character in the next segment cannot fit in that 1 cell
    # and must be dropped WHOLE (never split), same discipline `_clip_cells`
    # guarantees within a single unsegmented string.
    win = _RecordingWindow()
    draw_segment_line(win, BOXED_REGION, [("ABCDEFG", 1), ("あ", 2)], boxed=True)
    assert win.calls == [(1, 1, "ABCDEFG", 1)]  # the wide char never appears


def test_wide_char_that_fits_exactly_renders_in_full():
    # inner_w=8. First segment consumes 6 cells, leaving exactly 2 -- the
    # 2-cell CJK character in the next segment fits exactly.
    win = _RecordingWindow()
    draw_segment_line(win, BOXED_REGION, [("ABCDEF", 1), ("あ", 2)], boxed=True)
    assert win.calls == [(1, 1, "ABCDEF", 1), (1, 7, "あ", 2)]


def test_control_char_sanitized_to_space_across_segment_boundary():
    # An embedded control char (`\n`) inside one segment's text must never
    # reach `addstr` raw -- it would move the real terminal cursor and
    # escape the row. Sanitized to a plain space (alignment-preserving,
    # same char count) BEFORE the cell-width clip, same order as every
    # other write in this module.
    win = _RecordingWindow()
    draw_segment_line(win, BOXED_REGION, [("AB\nCD", 1), ("EFGH", 2)], boxed=True)
    # inner_w=8; "AB\nCD" sanitizes to "AB CD" (5 cells, unchanged length),
    # leaving 3 cells for "EFGH" -> clipped to "EFG".
    assert win.calls == [(1, 1, "AB CD", 1), (1, 6, "EFG", 2)]


def test_cross_segment_clip_matches_single_string_equivalent():
    # The running `remaining` budget carried across segment boundaries must
    # produce the IDENTICAL result a single `_clip_cells` call on the
    # segments' concatenated string would -- proven here by comparing
    # against `draw_lines`'s own single-attr rendering of the same
    # concatenated text at the same region/budget.
    from tw2002_aiclient.cockpit.draw import draw_lines

    combined_win = _RecordingWindow()
    draw_lines(combined_win, BOXED_REGION, ["ABCDEFGHIJ"], 0, boxed=True)
    (single_y, single_x, single_text, _attr) = combined_win.calls[0]

    segmented_win = _RecordingWindow()
    draw_segment_line(
        segmented_win, BOXED_REGION, [("ABCDE", 1), ("FGHIJ", 2)], boxed=True
    )
    joined = "".join(text for (_y, _x, text, _a) in segmented_win.calls)
    assert joined == single_text  # "ABCDEFGH" -- clipped to inner_w=8 either way
    assert segmented_win.calls[0][:3] == (single_y, single_x, "ABCDE")


def test_malformed_segments_are_dropped_survivors_still_render():
    win = _RecordingWindow()
    draw_segment_line(
        win,
        BOXED_REGION,
        [
            ("OK1", 1),
            123,  # not a 2-tuple at all -- TypeError on unpack, dropped
            ("too", "many", "values"),  # ValueError on unpack, dropped
            (5, 9),  # non-str text -- dropped
            ("OK2", 2),
        ],
        boxed=True,
    )
    assert win.calls == [(1, 1, "OK1", 1), (1, 4, "OK2", 2)]


def test_none_region_is_a_silent_noop():
    win = _RecordingWindow()
    draw_segment_line(win, None, [("x", 1)])
    assert win.calls == []


def test_empty_segments_is_a_silent_noop():
    win = _RecordingWindow()
    draw_segment_line(win, BOXED_REGION, [])
    assert win.calls == []


def test_unboxed_region_uses_raw_bounds_no_inset():
    win = _RecordingWindow()
    draw_segment_line(win, STRIP_REGION, [("AB", 7), ("CD", 8)], boxed=False)
    assert win.calls == [(5, 2, "AB", 7), (5, 4, "CD", 8)]


def test_zero_width_budget_renders_nothing():
    win = _RecordingWindow()
    draw_segment_line(
        win, {"y": 0, "x": 0, "w": 2, "h": 4}, [("x", 1)], boxed=True
    )  # boxed inner_w=0
    assert win.calls == []


# ---------------------------------------------------------------------------
# 2. Screens-level wiring matrix -- PlayShellScreen.draw() actually reaches
#    compose_control_strip_segments and paints each chip through its own
#    attr, proven via the fake-stdscr addstr-capture idiom this project's
#    own WO-P3-037 memory note points to (pyte can't see curses attrs at
#    all -- the fake window's own call log is the only way to prove one).
# ---------------------------------------------------------------------------

import pytest

from tw2002_aiclient.cockpit.control_seat import (
    MANUAL_LABEL,
    SPECTATE_LABEL,
    TRAINER_APP_ARMED_LABEL,
    TRAINER_MANUAL_HUMAN_LABEL,
)
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow

FULL_ROWS, FULL_COLS = 40, 180
HANDLE = "Alpha"

# The three canon-vocabulary labels never overlap as substrings of one
# another -- "APP" is not a substring of "SPECTATE" or "MANUAL — YOU HAVE
# CONTROL", and neither of those is a substring of the other -- so a plain
# `in` check against the reconstructed row text is an unambiguous presence
# test for each, no delimiter/boundary logic needed.
assert "APP" not in SPECTATE_LABEL
assert "APP" not in MANUAL_LABEL
assert SPECTATE_LABEL not in MANUAL_LABEL
assert MANUAL_LABEL not in SPECTATE_LABEL

# `PlayShellScreen.draw()` always renders through `trainer_labels=True`
# (WO-PLAY-STRIP-TRAINER-CHROME), so every real-draw assertion below reads
# the merged trainer chip, never the bare `APP_LABEL`/`MANUAL_LABEL` --
# the same non-overlap property holds for the trainer pair too.
assert SPECTATE_LABEL not in TRAINER_APP_ARMED_LABEL
assert SPECTATE_LABEL not in TRAINER_MANUAL_HUMAN_LABEL
assert TRAINER_APP_ARMED_LABEL not in TRAINER_MANUAL_HUMAN_LABEL
assert TRAINER_MANUAL_HUMAN_LABEL not in TRAINER_APP_ARMED_LABEL


class _RecordingWin:
    def __init__(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self):
        return (self._rows, self._cols)

    def erase(self):
        return None

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def refresh(self):
        return None


def _control_strip_frame(win: "_RecordingWin", rows: int, cols: int) -> list[tuple[str, int]]:
    """Reconstruct the LAST-drawn control-strip frame as an ordered list of
    ``(text, attr)`` segment calls -- mirrors ``tests/test_cockpit_attach.
    py::_control_strip_row_text``'s own "multiple addstr calls per row"
    reconstruction (WO-P5-060: ``draw_segment_line`` emits one call PER
    SEGMENT, since each carries its own attr), but keeps each segment's own
    attr instead of collapsing to a single string, so a test can assert
    chip text AND attr together in one pass."""
    regions = frame_layout(rows, cols)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    row_x = control_strip["x"]  # boxed=False -- no inset, this IS the write x
    row_calls = [
        (x, text, attr) for (y, x, text, attr) in win.calls if y == control_strip["y"]
    ]
    assert row_calls, "expected an addstr call on the control strip row"
    last_start = max(i for i, (x, _t, _a) in enumerate(row_calls) if x == row_x)
    return [(text, attr) for _x, text, attr in row_calls[last_start:]]


def _profile() -> ProfileRow:
    return ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )


@pytest.mark.parametrize(
    "spectating, attached, expected_label, expected_attr",
    [
        (True, False, SPECTATE_LABEL, curses.A_NORMAL),
        (False, True, TRAINER_MANUAL_HUMAN_LABEL, curses.A_BOLD | curses.A_REVERSE),
        (False, False, TRAINER_APP_ARMED_LABEL, curses.A_BOLD | curses.A_REVERSE),
    ],
    ids=["spectate-plain", "manual-warn-bold-reverse", "app-ok-bold-reverse"],
)
def test_wiring_matrix_chip_text_and_attr_per_state(
    monkeypatch, spectating, attached, expected_label, expected_attr
):
    """Canon badge law (`mode-line-and-teach-controls.md:179-181`):
    SPECTATE stays plain `A_NORMAL`; MANUAL (warn) and App (ok) both carry
    `A_BOLD | A_REVERSE` -- reverse-video applied to BOTH dual chips, not
    just the newly-added App side, so their register stays matched. Mono
    forced here (``has_colors=False``) isolates the attribute-only
    bold/reverse contract from real curses color-pair allocation, which
    ``_shared_pairs.attr_for`` degrades to bare ``A_NORMAL`` outside a real
    terminal anyway (same reason every other cockpit test in this project
    forces mono) -- the separate color-path tests below prove the color
    component is layered on TOP of, not instead of, this same bold/reverse
    pair via a monkeypatched ``_shared_pairs``."""
    monkeypatch.setattr(curses, "has_colors", lambda: False)

    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = PlayShellScreen(win, _profile())
    screen.spectating = spectating
    screen.attached = attached

    screen.draw()

    frame = _control_strip_frame(win, FULL_ROWS, FULL_COLS)
    label_text, label_attr = frame[0]
    assert label_text.startswith(expected_label)
    assert label_attr == expected_attr
    # The pre-existing liveness cluster must still be present -- the chip
    # never crowds it out at a real, roomy terminal width.
    joined = "".join(text for text, _attr in frame)
    assert "→" in joined


@pytest.mark.parametrize(
    "tone, expected_label",
    [("warn", TRAINER_MANUAL_HUMAN_LABEL), ("ok", TRAINER_APP_ARMED_LABEL)],
    ids=["manual-warn", "app-ok"],
)
def test_color_path_combines_allocated_pair_with_bold_reverse(monkeypatch, tone, expected_label):
    """The mono-mode matrix above proves the bold/reverse contract in
    isolation; this proves the color COMPONENT (`_shared_pairs.attr_for`'s
    own return) is layered ON TOP of it, not substituted for it. Real
    curses color-pair allocation needs a live terminal (every other test in
    this project's suite avoids it the same way) -- monkeypatching
    ``screens._shared_pairs.attr_for`` to a fake nonzero pair attr proves
    the OR-composition without one."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: True)
    fake_pair_attr = 128
    monkeypatch.setattr(
        screens_mod._shared_pairs, "attr_for", lambda fg, bg="default": fake_pair_attr
    )

    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = PlayShellScreen(win, _profile())
    screen.spectating = False
    screen.attached = tone == "warn"  # warn -> MANUAL (attached=True); ok -> APP (attached=False)

    screen.draw()

    frame = _control_strip_frame(win, FULL_ROWS, FULL_COLS)
    label_text, label_attr = frame[0]
    assert label_text.startswith(expected_label)
    assert label_attr == fake_pair_attr | curses.A_BOLD | curses.A_REVERSE


def test_xor_at_the_wire_exactly_one_chip_ever_renders(monkeypatch):
    """PWO-060's structural XOR guarantee, proven end-to-end through the
    real draw path (not just at the composer): across every reachable
    ``(spectating, attached)`` combo -- including the off-contract
    both-truthy case, where ``control_seat``'s own priority (attached wins)
    resolves it deterministically -- exactly ONE of SPECTATE/MANUAL/App
    ever appears in one rendered frame; App and MANUAL never co-render."""
    monkeypatch.setattr(curses, "has_colors", lambda: False)

    combos = [
        (True, False, SPECTATE_LABEL),
        (False, True, TRAINER_MANUAL_HUMAN_LABEL),
        (False, False, TRAINER_APP_ARMED_LABEL),
        # off-contract: attached wins (control_seat's own priority)
        (True, True, TRAINER_MANUAL_HUMAN_LABEL),
    ]
    for spectating, attached, expected_label in combos:
        win = _RecordingWin(FULL_ROWS, FULL_COLS)
        screen = PlayShellScreen(win, _profile())
        screen.spectating = spectating
        screen.attached = attached
        screen.draw()

        frame = _control_strip_frame(win, FULL_ROWS, FULL_COLS)
        joined = "".join(text for text, _attr in frame)
        present = {
            label
            for label in (SPECTATE_LABEL, TRAINER_MANUAL_HUMAN_LABEL, TRAINER_APP_ARMED_LABEL)
            if label in joined
        }
        assert present == {expected_label}, (spectating, attached, present)


def test_app_hold_to_manual_walk_app_chip_before_manual_after_never_both(monkeypatch):
    """WO-P5-061 Accept #6: a single screen instance walked App-hold ->
    (the Ctrl-A/attach-success field flip `app.py::_run_play` performs,
    WO-P5-061-ENTRY: the chord moved off `M` onto Ctrl-A) -> MANUAL, at
    the rendered-chip level. Proves APP renders BEFORE the transition and
    MANUAL AFTER, and that the two never co-render in either frame -- the
    same XOR guarantee ``test_xor_at_the_wire_exactly_one_chip_ever_
    renders`` above already proves per-state, now proven ACROSS a
    transition on one instance. The Ctrl-A keypress itself (the real
    daemon round trip) is exercised end-to-end by ``tests/
    test_cockpit_attach.py::
    test_app_hold_ctrl_a_attaches_to_human_lock_and_manual_chip_renders``;
    this test isolates the PAINT side only, mirroring how
    ``test_control_strip_transitions_spectate_manual_and_back`` (same
    sibling file) drives ``spectating``/``attached`` directly rather than
    a real attach round trip."""
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = PlayShellScreen(win, _profile())

    screen.spectating = False
    screen.attached = False  # App-hold -- driven directly (isolates the paint side)
    screen.draw()
    frame_before = _control_strip_frame(win, FULL_ROWS, FULL_COLS)
    joined_before = "".join(text for text, _attr in frame_before)
    present_before = {
        label
        for label in (SPECTATE_LABEL, TRAINER_MANUAL_HUMAN_LABEL, TRAINER_APP_ARMED_LABEL)
        if label in joined_before
    }
    assert present_before == {TRAINER_APP_ARMED_LABEL}

    win.calls.clear()
    screen.spectating = False
    screen.attached = True  # the Ctrl-A/attach-success flip -- app.py's own two-field set
    screen.draw()
    frame_after = _control_strip_frame(win, FULL_ROWS, FULL_COLS)
    joined_after = "".join(text for text, _attr in frame_after)
    present_after = {
        label
        for label in (SPECTATE_LABEL, TRAINER_MANUAL_HUMAN_LABEL, TRAINER_APP_ARMED_LABEL)
        if label in joined_after
    }
    assert present_after == {TRAINER_MANUAL_HUMAN_LABEL}
