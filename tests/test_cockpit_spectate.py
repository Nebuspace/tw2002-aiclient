"""PWO-055 -- product spectate state, Layer-A + a cheap fake-window wiring
proof (no real pty; the same ``_RecordingWin`` technique
``tests/test_cockpit_liveness_pty.py`` already uses to prove exactly what
landed in the control-strip row, without needing a spawned subprocess).

``tw2002_aiclient/cockpit/control_seat.py`` is the pure composer under test
here (``seat_label`` / ``compose_control_strip_line``); the second half of
this file proves ``PlayShellScreen.spectating`` actually reaches it through
``draw()``. Sibling file ``tests/test_spectate_no_send.py`` (lane B, not
touched here) covers the "no game-send path exists" side of this WO.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient.cockpit.control_seat import (
    MANUAL_LABEL,
    SPECTATE_LABEL,
    attached_label,
    compose_control_strip_line,
    seat_label,
)
from tw2002_aiclient.cockpit.layout import frame_layout

# ---------------------------------------------------------------------------
# seat_label -- pure, Layer-A
# ---------------------------------------------------------------------------


def test_seat_label_is_the_canon_cited_word():
    assert SPECTATE_LABEL == "SPECTATE"


def test_seat_label_true_renders_the_label():
    assert seat_label(True) == "SPECTATE"


def test_seat_label_false_yields_empty():
    assert seat_label(False) == ""


@pytest.mark.parametrize("truthy", [1, "yes", object(), [1], {"a": 1}])
def test_seat_label_any_truthy_value_renders_the_label(truthy):
    assert seat_label(truthy) == "SPECTATE"


@pytest.mark.parametrize("falsy", [0, "", [], {}, None])
def test_seat_label_any_falsy_value_yields_empty(falsy):
    assert seat_label(falsy) == ""


class _HostileBool:
    """A value whose truthiness genuinely cannot be evaluated -- mirrors
    ``cockpit.tones``'s own ``_HostileBool``-shaped hostile-input tests."""

    def __bool__(self):
        raise RuntimeError("truthiness unknown")


def test_seat_label_unevaluable_input_degrades_to_the_calm_spectate_reading():
    # Never raises; the honest-unknown default is SPECTATE (calm), not a
    # silently-invented "attached" claim -- see control_seat.py's own
    # `_safe_spectating` docstring for why this is the safe direction.
    assert seat_label(_HostileBool()) == "SPECTATE"


# ---------------------------------------------------------------------------
# compose_control_strip_line -- pure, Layer-A
# ---------------------------------------------------------------------------


def test_combines_label_left_and_liveness_right_with_full_width_result():
    line = compose_control_strip_line(spectating=True, liveness_text="● ⠋ → -", width=40)
    assert len(line) == 40
    assert line.startswith("SPECTATE")
    assert line.endswith("● ⠋ → -")


def test_not_spectating_renders_liveness_only_right_justified():
    line = compose_control_strip_line(spectating=False, liveness_text="● ⠋ → -", width=40)
    assert len(line) == 40
    assert "SPECTATE" not in line
    assert line.endswith("● ⠋ → -")
    assert line == "● ⠋ → -".rjust(40)


def test_matches_prior_behavior_when_not_spectating_and_width_positive():
    # Pre-PWO-055 wiring was exactly `liveness_text.rjust(cs_w)` -- pin the
    # equivalence explicitly for the not-spectating case so a future change
    # to this module can't silently regress the pre-existing liveness-only
    # rendering PWO-056 will still rely on once it flips `spectating=False`.
    liveness_text = "○ ⠹ → 158"
    assert compose_control_strip_line(
        spectating=False, liveness_text=liveness_text, width=30
    ) == liveness_text.rjust(30)


def test_zero_or_negative_width_yields_empty_string():
    assert compose_control_strip_line(spectating=True, liveness_text="x", width=0) == ""
    assert compose_control_strip_line(spectating=True, liveness_text="x", width=-5) == ""


def test_non_finite_width_never_raises():
    assert compose_control_strip_line(
        spectating=True, liveness_text="x", width=float("inf")
    ) == ""
    assert compose_control_strip_line(
        spectating=True, liveness_text="x", width=float("nan")
    ) == ""


def test_hostile_liveness_text_type_degrades_to_empty_liveness_not_a_crash():
    line = compose_control_strip_line(spectating=True, liveness_text=object(), width=20)
    assert len(line) == 20
    assert line.startswith("SPECTATE")


def test_label_drops_when_no_room_for_a_separator_column():
    # liveness_text alone exactly fills the row -- zero gap, label must not
    # collide with it.
    liveness_text = "x" * 20
    line = compose_control_strip_line(spectating=True, liveness_text=liveness_text, width=20)
    assert line == liveness_text
    assert "SPECTATE" not in line


def test_label_drops_when_gap_is_exactly_one_column():
    # Exactly one free column is reserved as the separator itself, not
    # enough room for even a single label character.
    liveness_text = "x" * 19
    line = compose_control_strip_line(spectating=True, liveness_text=liveness_text, width=20)
    assert line == liveness_text.rjust(20)
    assert "SPECTATE" not in line


def test_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column():
    liveness_text = "x" * 15
    line = compose_control_strip_line(spectating=True, liveness_text=liveness_text, width=20)
    assert len(line) == 20
    # gap == 5: 4 columns for the label (SPEC), 1 separator, 15 for liveness.
    assert line == "SPEC" + " " + liveness_text
    assert "SPECTATE" not in line  # truncated, not the full word


def test_empty_liveness_text_and_spectating_still_fits_label_alone():
    line = compose_control_strip_line(spectating=True, liveness_text="", width=20)
    assert len(line) == 20
    assert line.startswith("SPECTATE")
    assert line.strip() == "SPECTATE"


def test_unicode_ok_flag_has_no_effect_ascii_only_label():
    kwargs = dict(spectating=True, liveness_text="→ -", width=25)
    assert compose_control_strip_line(**kwargs, unicode_ok=True) == compose_control_strip_line(
        **kwargs, unicode_ok=False
    )


def test_never_raises_on_wildly_hostile_arguments():
    # spectating/liveness_text/width all hostile simultaneously.
    compose_control_strip_line(spectating=object(), liveness_text=object(), width="nope")


# ---------------------------------------------------------------------------
# Wiring proof -- PlayShellScreen.draw() actually reaches this composer.
# Fake-window technique (no real pty needed for this level of proof; mirrors
# tests/test_cockpit_liveness_pty.py's own `_RecordingWin`).
# ---------------------------------------------------------------------------

FULL_ROWS, FULL_COLS = 40, 160
HANDLE = "Alpha"


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


def _control_strip_row_text(win: "_RecordingWin", rows: int, cols: int) -> str:
    regions = frame_layout(rows, cols)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    row_calls = [text for (y, _x, text, _a) in win.calls if y == control_strip["y"]]
    assert row_calls, "expected an addstr call on the control strip row"
    return row_calls[-1]


def test_default_spectating_true_renders_seat_label_in_control_strip(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    assert screen.spectating is True  # the documented default

    screen.draw()

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert "SPECTATE" in row_text
    # the pre-existing liveness cluster must still be present -- the seat
    # label must never crowd it out at a real, roomy terminal width.
    assert "→" in row_text


def test_toggling_spectating_false_removes_the_label(monkeypatch):
    """Forward-compat proof for PWO-056: flipping the bool (the only change
    056 needs to make to reach this module) removes the SPECTATE marker and
    falls back to exactly the pre-PWO-055 liveness-only row -- 056 does not
    need to touch this module's signature to add its own attached state."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.spectating = False

    screen.draw()

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert "SPECTATE" not in row_text
    assert "→" in row_text


def test_control_strip_row_attr_is_muted_a_normal(monkeypatch):
    """Canon: Spectate is "muted / plain" -- achieved here for free because
    the whole control-strip row already draws in `curses.A_NORMAL` (default
    fg, non-bold); this pins that no new attr plumbing crept in."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    row_attrs = [attr for (y, _x, _t, attr) in win.calls if y == control_strip["y"]]
    assert row_attrs, "expected an addstr call on the control strip row"
    assert row_attrs[-1] == curses.A_NORMAL


def test_raising_control_seat_composer_does_not_crash_draw_and_liveness_survives(monkeypatch):
    """A raising `compose_control_strip_line` must not crash the draw pass
    -- same containment discipline every other composer call in `draw()`
    already has -- and falls back to the pre-existing liveness-only
    right-justified row rather than an empty one."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    def _raise(*a, **k):
        raise RuntimeError("composer is broken")

    monkeypatch.setattr(screens_mod.cockpit_control_seat, "compose_control_strip_line", _raise)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    screen.draw()  # must not raise

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert "SPECTATE" not in row_text
    assert "→" in row_text


def test_minimal_tier_still_renders_the_label_no_side_gutters(monkeypatch):
    """CONTROL_STRIP is present at every reachable non-too_small tier
    (layout.py's own comment) including `minimal`, where GOALS/DECISIONS/
    right_gutter are all absent -- the seat label must still reach that
    tier's control strip row."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    minimal_rows, minimal_cols = 25, 100
    regions = frame_layout(minimal_rows, minimal_cols)
    assert regions["mode"] == "minimal"
    assert regions["control_strip"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(minimal_rows, minimal_cols)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.draw()

    row_text = _control_strip_row_text(win, minimal_rows, minimal_cols)
    assert "SPECTATE" in row_text


def test_handle_key_unchanged_no_new_keys_from_this_wo(monkeypatch):
    """PWO-055 adds no keyboard handling of its own (spectate is the
    passive default, not a toggled affordance yet -- that's PWO-056's `h`)."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_RecordingWin(FULL_ROWS, FULL_COLS), profile)

    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("h")) is None
    assert screen.handle_key(ord("x")) is None


# ---------------------------------------------------------------------------
# WO-P4-056 lane B -- the "Human"/attached badge PWO-056 forecast above.
# Pure, Layer-A only: this file's own module docstring notes the DRAW-layer
# wiring (PlayShellScreen gaining its own `attached` state and passing it
# to `compose_control_strip_line`) is lane A's screens.py/app.py territory
# and had not landed as of this dispatch -- no wiring-proof section (no
# fake-window `PlayShellScreen.draw()` test) is added here for that reason;
# see this WO's own STATUS report for the honest scope statement.
# ---------------------------------------------------------------------------


def test_manual_label_is_the_canon_cited_word():
    assert MANUAL_LABEL == "MANUAL — YOU HAVE CONTROL"


def test_attached_label_true_renders_the_label():
    assert attached_label(True) == "MANUAL — YOU HAVE CONTROL"


def test_attached_label_false_yields_empty():
    assert attached_label(False) == ""


@pytest.mark.parametrize("truthy", [1, "yes", object(), [1], {"a": 1}])
def test_attached_label_any_truthy_value_renders_the_label(truthy):
    assert attached_label(truthy) == MANUAL_LABEL


@pytest.mark.parametrize("falsy", [0, "", [], {}, None])
def test_attached_label_any_falsy_value_yields_empty(falsy):
    assert attached_label(falsy) == ""


def test_attached_label_unevaluable_input_degrades_to_no_claim():
    # Opposite default from seat_label's own unevaluable case: an unknown
    # `attached` must not invent the more consequential "you have control"
    # claim -- see control_seat.py's own `_safe_attached` docstring.
    assert attached_label(_HostileBool()) == ""


def test_compose_control_strip_line_default_attached_is_false_backward_compat():
    # Every pre-PWO-056 call site (screens.py's own, and every test above
    # in this file) omits `attached` entirely -- the new parameter's
    # default must reproduce the exact pre-existing behavior.
    kwargs = dict(spectating=True, liveness_text="● ⠋ → -", width=40)
    assert compose_control_strip_line(**kwargs) == compose_control_strip_line(
        **kwargs, attached=False
    )


def test_attached_true_renders_manual_label_left_anchored():
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="● ⠋ → -", width=40
    )
    assert len(line) == 40
    assert line.startswith(MANUAL_LABEL)
    assert line.endswith("● ⠋ → -")


def test_attached_true_wins_over_spectating_true():
    # Off-contract (the two are mutually exclusive by construction -- see
    # compose_control_strip_line's own docstring) but must resolve
    # deterministically rather than crash or silently pick the calmer one.
    line = compose_control_strip_line(
        spectating=True, attached=True, liveness_text="x", width=40
    )
    assert MANUAL_LABEL in line
    assert "SPECTATE" not in line


def test_attached_false_and_spectating_false_renders_liveness_only():
    liveness_text = "○ ⠹ → 158"
    line = compose_control_strip_line(
        spectating=False, attached=False, liveness_text=liveness_text, width=30
    )
    assert line == liveness_text.rjust(30)


def test_manual_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column():
    liveness_text = "x" * 15
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text=liveness_text, width=20
    )
    assert len(line) == 20
    # gap == 5: 4 columns for the label, 1 separator, 15 for liveness.
    assert line == MANUAL_LABEL[:4] + " " + liveness_text
    assert MANUAL_LABEL not in line  # truncated, not the full phrase


def test_manual_label_drops_when_no_room_for_a_separator_column():
    liveness_text = "x" * 20
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text=liveness_text, width=20
    )
    assert line == liveness_text
    assert "MANUAL" not in line


def test_unicode_ok_flag_has_no_effect_on_manual_label_either():
    # MANUAL_LABEL's embedded em-dash is canon's own NO-SWAP glyph (see
    # control_seat.py's own MANUAL_LABEL comment) -- unicode_ok=False must
    # not strip or substitute it.
    kwargs = dict(spectating=False, attached=True, liveness_text="→ -", width=30)
    assert compose_control_strip_line(**kwargs, unicode_ok=True) == compose_control_strip_line(
        **kwargs, unicode_ok=False
    )
    assert "—" in compose_control_strip_line(**kwargs, unicode_ok=False)


def test_never_raises_with_hostile_attached_argument_too():
    compose_control_strip_line(
        spectating=object(), attached=object(), liveness_text=object(), width="nope"
    )
