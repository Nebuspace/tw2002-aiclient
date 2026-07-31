"""PWO-055 -- product spectate state, Layer-A + a cheap fake-window wiring
proof (no real pty; the same ``_RecordingWin`` technique
``tests/test_cockpit_liveness_pty.py`` already uses to prove exactly what
landed in the control-strip row, without needing a spawned subprocess).

``tw2002_aiclient/cockpit/control_seat.py`` is the pure composer under test
here (``seat_label`` / ``compose_control_strip_segments``); the second half of
this file proves ``PlayShellScreen.spectating`` actually reaches it through
``draw()``. Sibling file ``tests/test_spectate_no_send.py`` (lane B, not
touched here) covers the "no game-send path exists" side of this WO.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient.cockpit.control_seat import (
    APP_LABEL,
    MANUAL_LABEL,
    SPECTATE_LABEL,
    TRAINER_MANUAL_HUMAN_LABEL,
    app_label,
    attached_label,
    compose_control_strip_segments,
    seat_label,
)
from tw2002_aiclient.cockpit.layout import frame_layout

def _joined_strip(**kwargs) -> str:
    """Flat join of ``compose_control_strip_segments`` — test-only stand-in
    for the retired product flat-string strip helper."""
    return "".join(text for text, _tone in compose_control_strip_segments(**kwargs))


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
# compose_control_strip_segments (joined) -- pure, Layer-A
# ---------------------------------------------------------------------------


def test_combines_label_left_and_liveness_right_with_full_width_result():
    line = _joined_strip(spectating=True, liveness_text="● ⠋ → -", width=40)
    assert len(line) == 40
    assert line.startswith("SPECTATE")
    assert line.endswith("● ⠋ → -")


def test_not_spectating_renders_liveness_only_right_justified():
    # spectating=False with `attached` at its default (False) is the
    # PWO-060 App fallback -- both flags falsy is now App, not a bare
    # liveness-only row. See test_neither_spectating_nor_attached_renders_
    # app_label_left_anchored (PWO-060 section) for the dedicated App test;
    # this one keeps its original name/scope (spectating=False specifically
    # does not render SPECTATE) but its liveness-only assertion is gone.
    line = _joined_strip(spectating=False, liveness_text="● ⠋ → -", width=40)
    assert len(line) == 40
    assert "SPECTATE" not in line
    assert line.endswith("● ⠋ → -")


def test_matches_prior_behavior_when_not_spectating_and_width_positive():
    # RETIRED premise (pre-PWO-060): this test used to pin that not-
    # spectating renders exactly `liveness_text.rjust(cs_w)` -- true only
    # because "spectating=False, attached=False" was previously an
    # off-contract combo with no defined rendering of its own. PWO-060
    # gives that combo real meaning (App, the dual's third/terminal chip --
    # see control_seat.py's own module docstring), so the old "matches
    # prior behavior" premise is retired, not merely broken: the row must
    # now show the App label rather than bare liveness.
    liveness_text = "○ ⠹ → 158"
    line = _joined_strip(spectating=False, liveness_text=liveness_text, width=30)
    assert line != liveness_text.rjust(30)
    assert line.startswith(APP_LABEL)
    assert line.endswith(liveness_text)


def test_zero_or_negative_width_yields_empty_string():
    assert _joined_strip(spectating=True, liveness_text="x", width=0) == ""
    assert _joined_strip(spectating=True, liveness_text="x", width=-5) == ""


def test_non_finite_width_never_raises():
    assert _joined_strip(
        spectating=True, liveness_text="x", width=float("inf")
    ) == ""
    assert _joined_strip(
        spectating=True, liveness_text="x", width=float("nan")
    ) == ""


def test_hostile_liveness_text_type_degrades_to_empty_liveness_not_a_crash():
    line = _joined_strip(spectating=True, liveness_text=object(), width=20)
    assert len(line) == 20
    assert line.startswith("SPECTATE")


def test_label_drops_when_no_room_for_a_separator_column():
    # liveness_text alone exactly fills the row -- zero gap, label must not
    # collide with it.
    liveness_text = "x" * 20
    line = _joined_strip(spectating=True, liveness_text=liveness_text, width=20)
    assert line == liveness_text
    assert "SPECTATE" not in line


def test_label_drops_when_gap_is_exactly_one_column():
    # Exactly one free column is reserved as the separator itself, not
    # enough room for even a single label character.
    liveness_text = "x" * 19
    line = _joined_strip(spectating=True, liveness_text=liveness_text, width=20)
    assert line == liveness_text.rjust(20)
    assert "SPECTATE" not in line


def test_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column():
    liveness_text = "x" * 15
    line = _joined_strip(spectating=True, liveness_text=liveness_text, width=20)
    assert len(line) == 20
    # gap == 5: 4 columns for the label (SPEC), 1 separator, 15 for liveness.
    assert line == "SPEC" + " " + liveness_text
    assert "SPECTATE" not in line  # truncated, not the full word


def test_empty_liveness_text_and_spectating_still_fits_label_alone():
    line = _joined_strip(spectating=True, liveness_text="", width=20)
    assert len(line) == 20
    assert line.startswith("SPECTATE")
    assert line.strip() == "SPECTATE"


def test_unicode_ok_flag_has_no_effect_ascii_only_label():
    kwargs = dict(spectating=True, liveness_text="→ -", width=25)
    assert _joined_strip(**kwargs, unicode_ok=True) == _joined_strip(
        **kwargs, unicode_ok=False
    )


def test_never_raises_on_wildly_hostile_arguments():
    # spectating/liveness_text/width all hostile simultaneously.
    _joined_strip(spectating=object(), liveness_text=object(), width="nope")


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


def _control_strip_row_calls(
    win: "_RecordingWin", rows: int, cols: int
) -> list[tuple[int, str, int]]:
    """All of THIS row's own content ``addstr`` calls, sorted left-to-right
    by x -- excludes the outer double-line frame's own left/right border
    columns (drawn at ``x`` outside ``control_strip``'s own ``[x, x+w)``
    span, which coincidentally land on the same ``y`` as the control
    strip's own row -- both edges must be bounded, not just the left one,
    or the right border leaks through as a trailing call). WO-P5-060 note:
    ``draw_segment_line`` (``cockpit/draw.py``) writes ONE ``addstr`` call
    PER SEGMENT rather than one call for the whole row -- a real,
    deliberate landed change (the mode-badge chip now needs its own
    reverse-video+tone attr distinct from the plain liveness cluster), not
    a bug -- so callers here must reconstruct the row from every content
    call in x-order, not assume there is exactly one."""
    regions = frame_layout(rows, cols)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    lo, hi = control_strip["x"], control_strip["x"] + control_strip["w"]
    calls = sorted(
        (x, text, attr)
        for (y, x, text, attr) in win.calls
        if y == control_strip["y"] and lo <= x < hi
    )
    assert calls, "expected an addstr call on the control strip row"
    return calls


def _control_strip_row_text(win: "_RecordingWin", rows: int, cols: int) -> str:
    return "".join(text for _x, text, _attr in _control_strip_row_calls(win, rows, cols))


def test_entry_default_renders_app_chip_matching_the_daemons_own_mode(monkeypatch):
    """RENAMED + RE-JUSTIFIED (prior name: ``test_default_spectating_true_
    renders_seat_label_in_control_strip``, whose premise -- "a fresh
    cockpit is Spectating" -- is now FALSE).

    WO-ENTRY-APP-CHIP is a code-to-canon correction, not a new product
    decision. Canon has said this prescriptively all along --
    ``canon/surfaces/mode-line-and-teach-controls.md:39``: "Default when
    the client runs = App/autopilot" -- ratified in ADR-002 (Accepted
    2026-07-25, ``canon/ADR/002-mode-chord-ctrl-a.md:30``: "Spectate is
    not a Mode; default run = App/autopilot"; :39: "Spectate remains
    observation chrome only -- not a third dual position"). The entry
    chip must therefore report the seat-holder the DAEMON actually has at
    that same instant, and that fact is citable, not assumed:
    ``session/control_lock.py:59`` constructs ``self._mode = MODE_APP``,
    and ``app.py::_run_play`` takes the Human lock only in response to a
    Ctrl-A keypress that has not happened yet on a freshly-constructed
    cockpit. So daemon truth at entry is App; the old ``spectating = True``
    default made this screen open by asserting a state the daemon was not
    in (and which the ruling has since removed from the Mode vocabulary
    altogether).

    App-hold is the client-side mirror of that daemon fact -- the literal
    ``spectating is False and attached is False`` pair
    ``control_seat.py``'s own ``_is_definitively_false`` gate requires
    before it will render ``APP_LABEL`` at all. This test pins the whole
    chain: the two entry fields, and the chip that actually reaches the
    control-strip row because of them.

    Spectate is NOT removed by this change -- it remains the post-detach
    observation state (``app.py``'s Ctrl-] branch sets ``spectating =
    True``); ``tests/test_cockpit_attach.py::test_control_strip_chip_
    restores_to_spectate_after_detach`` proves it still paints, through a
    real detach round trip."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    # App-hold, both literally False -- the documented entry default.
    assert screen.spectating is False
    assert screen.attached is False

    screen.draw()

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert APP_LABEL in row_text
    assert SPECTATE_LABEL not in row_text  # the state the daemon is NOT in
    assert MANUAL_LABEL not in row_text  # nor is the human holding the lock yet
    # the pre-existing liveness cluster must still be present -- the mode
    # chip must never crowd it out at a real, roomy terminal width.
    assert "→" in row_text


def test_entry_default_mirrors_a_freshly_constructed_control_locks_own_mode():
    """The other half of the citation above, executed rather than quoted:
    a freshly-constructed ``ControlLock`` -- no ``take_human()``, no
    ``enter_auto_loop()`` -- reports ``MODE_APP``, so the cockpit's own
    entry App-hold pair is a reflection of a real daemon-side default, not
    a client-side invention. Sibling of ``tests/test_cockpit_attach.py::
    test_app_hold_daemon_seat_truth_default_mode_is_app_not_a_client_
    fiction``; kept here so this file's entry-chip pin carries its own
    daemon-truth leg rather than depending on a cross-file read."""
    from tw2002_aiclient.session.control_lock import MODE_APP, ControlLock

    assert ControlLock().mode == MODE_APP


def test_returning_from_spectate_to_app_hold_renders_app_not_liveness_only(monkeypatch):
    """RENAMED TWICE, and the reason matters both times.

    Pre-WO-P5-060 it was ``..._removes_the_label`` and claimed a "falls
    back to liveness-only" outcome -- a premise that died with the old
    ``attached=not self.spectating`` derivation.

    WO-P5-060 renamed it to ``test_toggling_spectating_false_alone_...``,
    which was accurate only while ``spectating`` STARTED ``True``: the
    assignment below was a genuine toggle off the entry default.
    WO-ENTRY-APP-CHIP makes ``False`` the entry default, so "toggling
    false" would now describe a no-op assignment -- a quietly false name.
    What the test still genuinely covers is the RETURN leg: a client that
    has been parked in post-detach Spectate (``app.py``'s Ctrl-] branch is
    the real writer of ``spectating = True``) and then goes back to
    App-hold must paint the App chip, not fall through to a liveness-only
    row. So the Spectate starting state is now driven explicitly rather
    than inherited from a default, and the walk is stated in full.

    See ``test_toggling_spectating_false_and_attached_true_renders_manual``
    below for the "switch to Human" scenario, and
    ``test_entry_default_renders_app_chip_matching_the_daemons_own_mode``
    above for the entry state this one no longer stands in for."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    # Post-detach observation state, driven explicitly -- no longer the
    # constructor's own default.
    screen.spectating = True
    screen.attached = False
    screen.draw()
    assert SPECTATE_LABEL in _control_strip_row_text(win, FULL_ROWS, FULL_COLS)

    win.calls.clear()
    screen.spectating = False
    assert screen.attached is False  # untouched -- both now literally False

    screen.draw()

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert SPECTATE_LABEL not in row_text
    assert APP_LABEL in row_text
    assert MANUAL_LABEL not in row_text
    assert "→" in row_text


def test_toggling_spectating_false_and_attached_true_renders_manual(monkeypatch):
    """The genuine "switch to Human" wiring proof WO-P5-060's own screens.py
    landing enables: both flags set independently and explicitly, the way
    the real Ctrl-A/attach call sites do (WO-P5-061-ENTRY moved the chord
    off `M`; `self.attached` is no longer derived from `self.spectating`)."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.spectating = False
    screen.attached = True

    screen.draw()

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert "SPECTATE" not in row_text
    assert APP_LABEL not in row_text
    # WO-PLAY-STRIP-TRAINER-CHROME: the real cockpit draws the merged
    # trainer chip (`trainer_labels=True`), not the bare `MANUAL_LABEL`.
    assert TRAINER_MANUAL_HUMAN_LABEL in row_text
    assert "→" in row_text


def test_control_strip_row_attr_is_muted_a_normal(monkeypatch):
    """Canon: Spectate is "muted / plain" -- achieved here for free because
    every content segment on this row draws in `curses.A_NORMAL` (default
    fg, non-bold) while `spectating` is the active chip; this pins that no
    new attr plumbing crept in for the SPECTATE case specifically. WO-P5-060
    note: `draw_segment_line` now writes one `addstr` call PER SEGMENT
    (see `_control_strip_row_calls`'s own docstring), so this checks EVERY
    content call's attr, not just the last one -- the App/MANUAL chips
    legitimately carry a different (reverse-video+tone) attr of their own
    once PWO-061 makes them reachable; this test only pins the SPECTATE
    case's own attr, which is unaffected by that.

    WO-ENTRY-APP-CHIP: the Spectate state is now driven EXPLICITLY below.
    It used to be inherited from the constructor's `spectating = True`
    default, so this test read as an entry-state assertion even though its
    own docstring has always scoped itself to "the SPECTATE case"; with
    App-hold the entry default, leaving that implicit would have silently
    turned this into an assertion about the APP chip -- which legitimately
    carries `A_BOLD | A_REVERSE` and would have gone red for the wrong
    reason.

    WO-P5-062 (NARROWED, and narrowed to what this docstring has always
    claimed to pin): the assertion below used to sweep EVERY content call
    on the row. That was a sound implementation of "the SPECTATE case's
    own attr" only for as long as the seat chip was the row's sole
    tone-carrying candidate. WO-P5-062 adds the autopilot ARM chip beside
    it -- a genuinely independent fact with its own tone (`ARM ?` renders
    `A_BOLD | A_REVERSE` at the unknown reading) -- so the whole-row sweep
    now fails for a chip this test was never about, the third time this
    same over-reach has surfaced here. The check is therefore scoped to
    the SPECTATE segment itself, which is the canon claim (`visual-
    language.md`: Spectate is muted/plain, deliberately uncolored). It
    keeps its teeth: BOLD and REVERSE are asserted absent individually, so
    a future change that promoted the SPECTATE chip to a badge still goes
    red here rather than passing on a loosened assertion."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.spectating = True  # post-detach observation state, driven explicitly
    screen.attached = False
    screen.draw()

    assert SPECTATE_LABEL in _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    calls = _control_strip_row_calls(win, FULL_ROWS, FULL_COLS)
    spectate_calls = [(x, t, attr) for x, t, attr in calls if SPECTATE_LABEL in t]
    assert spectate_calls, (
        f"the SPECTATE chip was not drawn as its own segment; row was {calls!r}"
    )
    for _x, _t, attr in spectate_calls:
        assert attr == curses.A_NORMAL, calls
        assert not attr & curses.A_BOLD, calls
        assert not attr & curses.A_REVERSE, calls


def test_raising_control_seat_composer_does_not_crash_draw_and_liveness_survives(monkeypatch):
    """A raising `compose_control_strip_segments` (WO-P5-060: this is the
    function `draw()` actually calls now, replacing the flat-string
    `compose_control_strip_segments` call this test used to monkeypatch) must
    not crash the draw pass -- same containment discipline every other
    composer call in `draw()` already has -- and falls back to the
    pre-existing liveness-only right-justified row rather than an empty
    one.

    WO-ENTRY-APP-CHIP: the "no chip survived" assertion below now names
    APP as well as SPECTATE. It used to name SPECTATE alone, which was
    load-bearing only because SPECTATE was the entry chip -- with App-hold
    the entry state, a SPECTATE-only absence check would pass whether the
    fallback fired or not. The chip that WOULD be on this row absent the
    fallback has to be the one whose absence is asserted."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    def _raise(*a, **k):
        raise RuntimeError("composer is broken")

    monkeypatch.setattr(screens_mod.cockpit_control_seat, "compose_control_strip_segments", _raise)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    screen.draw()  # must not raise

    row_text = _control_strip_row_text(win, FULL_ROWS, FULL_COLS)
    assert APP_LABEL not in row_text  # the chip this entry state WOULD have painted
    assert SPECTATE_LABEL not in row_text
    assert MANUAL_LABEL not in row_text
    assert "→" in row_text


def test_minimal_tier_still_renders_the_label_no_side_gutters(monkeypatch):
    """CONTROL_STRIP is present at every reachable non-too_small tier
    (layout.py's own comment) including `minimal`, where GOALS/DECISIONS/
    right_gutter are all absent -- the seat label must still reach that
    tier's control strip row.

    WO-ENTRY-APP-CHIP: both chips are checked at this tier now. The
    SPECTATE leg is what this test has always been about (it is this
    file's own subject), but it used to arrive via the constructor's
    `spectating = True` default; that default is now App-hold, so the
    Spectate state is driven explicitly and the entry APP chip is checked
    alongside it -- the tier's chip plumbing is chip-agnostic, and pinning
    only one of them would leave the tier untested for whichever chip the
    entry default happens to be."""
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

    screen.draw()  # entry state -- App-hold
    assert APP_LABEL in _control_strip_row_text(win, minimal_rows, minimal_cols)

    win.calls.clear()
    screen.spectating = True  # post-detach observation state
    screen.attached = False
    screen.draw()

    row_text = _control_strip_row_text(win, minimal_rows, minimal_cols)
    assert SPECTATE_LABEL in row_text


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
# to `compose_control_strip_segments`) is lane A's screens.py/app.py territory
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


def test_compose_control_strip_segments_default_attached_is_false_backward_compat():
    # Every pre-PWO-056 call site (screens.py's own, and every test above
    # in this file) omits `attached` entirely -- the new parameter's
    # default must reproduce the exact pre-existing behavior.
    kwargs = dict(spectating=True, liveness_text="● ⠋ → -", width=40)
    assert _joined_strip(**kwargs) == _joined_strip(
        **kwargs, attached=False
    )


def test_attached_true_renders_manual_label_left_anchored():
    line = _joined_strip(
        spectating=False, attached=True, liveness_text="● ⠋ → -", width=40
    )
    assert len(line) == 40
    assert line.startswith(MANUAL_LABEL)
    assert line.endswith("● ⠋ → -")


def test_attached_true_wins_over_spectating_true():
    # Off-contract (the two are mutually exclusive by construction -- see
    # compose_control_strip_segments' own docstring) but must resolve
    # deterministically rather than crash or silently pick the calmer one.
    line = _joined_strip(
        spectating=True, attached=True, liveness_text="x", width=40
    )
    assert MANUAL_LABEL in line
    assert "SPECTATE" not in line


def test_attached_false_and_spectating_false_renders_app_label():
    # RENAMED from ..._renders_liveness_only (pre-PWO-060): both flags
    # falsy is now the documented App fallback, not liveness-only -- see
    # test_matches_prior_behavior_when_not_spectating_and_width_positive's
    # comment above for the full "retired premise" explanation.
    liveness_text = "○ ⠹ → 158"
    line = _joined_strip(
        spectating=False, attached=False, liveness_text=liveness_text, width=30
    )
    assert line != liveness_text.rjust(30)
    assert line.startswith(APP_LABEL)
    assert line.endswith(liveness_text)


def test_manual_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column():
    liveness_text = "x" * 15
    line = _joined_strip(
        spectating=False, attached=True, liveness_text=liveness_text, width=20
    )
    assert len(line) == 20
    # gap == 5: 4 columns for the label, 1 separator, 15 for liveness.
    assert line == MANUAL_LABEL[:4] + " " + liveness_text
    assert MANUAL_LABEL not in line  # truncated, not the full phrase


def test_manual_label_drops_when_no_room_for_a_separator_column():
    liveness_text = "x" * 20
    line = _joined_strip(
        spectating=False, attached=True, liveness_text=liveness_text, width=20
    )
    assert line == liveness_text
    assert "MANUAL" not in line


def test_unicode_ok_flag_has_no_effect_on_manual_label_either():
    # MANUAL_LABEL's embedded em-dash is canon's own NO-SWAP glyph (see
    # control_seat.py's own MANUAL_LABEL comment) -- unicode_ok=False must
    # not strip or substitute it.
    kwargs = dict(spectating=False, attached=True, liveness_text="→ -", width=30)
    assert _joined_strip(**kwargs, unicode_ok=True) == _joined_strip(
        **kwargs, unicode_ok=False
    )
    assert "—" in _joined_strip(**kwargs, unicode_ok=False)


def test_never_raises_with_hostile_attached_argument_too():
    _joined_strip(
        spectating=object(), attached=object(), liveness_text=object(), width="nope"
    )


# ---------------------------------------------------------------------------
# WO-P5-060 lane A -- the App chip and compose_control_strip_segments.
# Pure, Layer-A only: no wiring-proof section here (screens.py wiring is
# lane B's own territory, run concurrently against the pinned API this
# module exposes -- see control_seat.py's own PWO-060 module-docstring
# note, including the two points flagged to the team lead pre-build: the
# selection priority stays attached > spectating > App (matching the
# ALREADY-SHIPPED strip priority pinned above by
# test_attached_true_wins_over_spectating_true), not the dispatch's
# literal "spectating first" wording, and the strip composer
# itself gained the App fallback branch so the concatenation invariant
# below can hold across the full input matrix.
# ---------------------------------------------------------------------------


def test_app_label_is_the_canon_cited_word():
    assert APP_LABEL == "APP"


def test_app_label_function_always_returns_the_label():
    # Unlike seat_label/attached_label, app_label() takes no argument --
    # App is the terminal fallback, never independently toggled.
    assert app_label() == "APP"


def test_app_label_never_the_retired_vocabulary():
    assert APP_LABEL not in ("AI-PILOT", "AUTO-LOOP")


# --- Selection matrix (explicit, readable cases) ---------------------------


def test_selection_matrix_spectating_true_attached_false_is_spectate():
    line = _joined_strip(spectating=True, attached=False, liveness_text="x", width=30)
    assert line.startswith(SPECTATE_LABEL)


def test_selection_matrix_spectating_false_attached_true_is_manual():
    line = _joined_strip(spectating=False, attached=True, liveness_text="x", width=30)
    assert line.startswith(MANUAL_LABEL)


def test_selection_matrix_spectating_false_attached_false_is_app():
    line = _joined_strip(spectating=False, attached=False, liveness_text="x", width=30)
    assert line.startswith(APP_LABEL)


def test_selection_matrix_both_truthy_attached_wins_not_app_not_spectate():
    # Off-contract (056's own precedent: the caller's real state never sets
    # both truthy), but must resolve deterministically -- attached wins,
    # matching the pre-existing test_attached_true_wins_over_spectating_true.
    line = _joined_strip(spectating=True, attached=True, liveness_text="x", width=30)
    assert line.startswith(MANUAL_LABEL)
    assert APP_LABEL not in line
    assert SPECTATE_LABEL not in line


def test_neither_spectating_nor_attached_renders_app_label_left_anchored():
    line = _joined_strip(
        spectating=False, attached=False, liveness_text="● ⠋ → -", width=40
    )
    assert len(line) == 40
    assert line.startswith(APP_LABEL)
    assert line.endswith("● ⠋ → -")
    assert MANUAL_LABEL not in line
    assert SPECTATE_LABEL not in line


# --- compose_control_strip_segments -- tone assignment ---------------------


def test_segments_app_chip_carries_ok_tone():
    segs = compose_control_strip_segments(
        spectating=False, attached=False, liveness_text="x", width=30
    )
    label_segs = [seg for seg in segs if seg[0].strip() == APP_LABEL]
    assert label_segs, segs
    assert label_segs[0][1] == "ok"


def test_segments_manual_chip_carries_warn_tone():
    segs = compose_control_strip_segments(
        spectating=False, attached=True, liveness_text="x", width=30
    )
    label_segs = [seg for seg in segs if seg[0].strip() == MANUAL_LABEL]
    assert label_segs, segs
    assert label_segs[0][1] == "warn"


def test_segments_spectate_chip_carries_no_tone_stays_plain():
    # Explicit hub constraint: SPECTATE stays a None/plain segment, never
    # restyled, even though this composer now carries a tone channel.
    segs = compose_control_strip_segments(
        spectating=True, attached=False, liveness_text="x", width=30
    )
    label_segs = [seg for seg in segs if seg[0].strip() == SPECTATE_LABEL]
    assert label_segs, segs
    assert label_segs[0][1] is None


def test_segments_default_arguments_are_spectating_true_attached_false():
    # Pinned defaults from the dispatch's own signature -- calling with no
    # kwargs at all must behave like the documented spectating=True default.
    assert compose_control_strip_segments(liveness_text="x", width=30) == (
        compose_control_strip_segments(spectating=True, attached=False, liveness_text="x", width=30)
    )


def test_segments_invalid_width_returns_empty_list():
    assert compose_control_strip_segments(spectating=True, liveness_text="x", width=0) == []
    assert compose_control_strip_segments(spectating=True, liveness_text="x", width=-5) == []
    assert compose_control_strip_segments(
        spectating=True, liveness_text="x", width=float("nan")
    ) == []


def test_segments_unicode_ok_flag_has_no_effect():
    kwargs = dict(spectating=False, attached=False, liveness_text="→ -", width=25)
    assert compose_control_strip_segments(
        **kwargs, unicode_ok=True
    ) == compose_control_strip_segments(**kwargs, unicode_ok=False)


def test_segments_never_raises_on_wildly_hostile_arguments():
    compose_control_strip_segments(
        spectating=object(), attached=object(), liveness_text=object(), width="nope"
    )


# --- Concatenation invariant -- the anti-drift guarantee --------------------


_CONCAT_FLAG_VALUES = [True, False]
_CONCAT_WIDTHS = [0, 1, 2, 3, 4, 5, 8, 15, 20, 30, 40, 60]
_CONCAT_LIVENESS_TEXTS = ["", "x", "x" * 15, "x" * 20, "● ⠋ → -", "○ ⠹ → 158"]


@pytest.mark.parametrize("spectating", _CONCAT_FLAG_VALUES)
@pytest.mark.parametrize("attached", _CONCAT_FLAG_VALUES)
@pytest.mark.parametrize("width", _CONCAT_WIDTHS)
@pytest.mark.parametrize("liveness_text", _CONCAT_LIVENESS_TEXTS)
def test_segments_join_width_and_xor_tone(
    spectating, attached, width, liveness_text
):
    segs = compose_control_strip_segments(
        spectating=spectating, attached=attached, liveness_text=liveness_text, width=width
    )
    joined = "".join(text for text, _tone in segs)
    if isinstance(width, int) and width > 0:
        assert len(joined) == width
    else:
        assert joined == ""
    # XOR structural pin: never more than one tone-carrying (App or MANUAL) segment.
    toned = [seg for seg in segs if seg[1] is not None]
    assert len(toned) <= 1


# --- Width-pressure behavior for the App chip (mirrors the SPECTATE and
# MANUAL drop-policy tests above) -------------------------------------------


def test_app_label_drops_when_no_room_for_a_separator_column():
    liveness_text = "x" * 20
    line = _joined_strip(
        spectating=False, attached=False, liveness_text=liveness_text, width=20
    )
    assert line == liveness_text
    assert APP_LABEL not in line


def test_app_label_drops_when_gap_is_exactly_one_column():
    liveness_text = "x" * 19
    line = _joined_strip(
        spectating=False, attached=False, liveness_text=liveness_text, width=20
    )
    assert line == liveness_text.rjust(20)
    assert APP_LABEL not in line


def test_app_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column():
    # APP_LABEL is 3 chars; gap == 3 leaves only 2 columns for the label.
    liveness_text = "x" * 17
    line = _joined_strip(
        spectating=False, attached=False, liveness_text=liveness_text, width=20
    )
    assert len(line) == 20
    assert line == APP_LABEL[:2] + " " + liveness_text


def test_app_label_renders_in_full_with_a_generous_gap():
    liveness_text = "x" * 15
    line = _joined_strip(
        spectating=False, attached=False, liveness_text=liveness_text, width=20
    )
    assert len(line) == 20
    # gap == 5: APP_LABEL (3 chars) fits whole, 1 separator, 15 liveness.
    assert line == APP_LABEL + "  " + liveness_text


def test_app_label_empty_liveness_text_still_fits_label_alone():
    line = _joined_strip(spectating=False, attached=False, liveness_text="", width=20)
    assert len(line) == 20
    assert line.strip() == APP_LABEL


# --- Degrade matrix, incl. garbage/raising inputs ---------------------------


_DEGRADE_MATRIX_INPUTS = [
    True, False, None, 1, 0, "", "x", object(), [], [1], {}, {"a": 1}, _HostileBool(),
]


@pytest.mark.parametrize("spectating", _DEGRADE_MATRIX_INPUTS)
@pytest.mark.parametrize("attached", _DEGRADE_MATRIX_INPUTS)
def test_degrade_matrix_label_matches_priority_oracle_and_never_raises(spectating, attached):
    width = 60
    # Oracle: the module's own already-tested primitives, not a
    # reimplementation of their truthiness logic in this test -- plus the
    # team-lead-mandated App-eligibility gate folded in explicitly (App
    # only when BOTH raw inputs are the literal `False` singleton, never a
    # coerced/degraded/garbage falsy reading -- see control_seat.py's own
    # `_is_definitively_false`). Unlike the pre-hardening version of this
    # oracle, `expected_label` can now legitimately be `""` (neither claim
    # survives, e.g. spectating=None, attached=None) -- that is a real,
    # correct outcome (liveness-only), not a gap in the oracle.
    expected_label = attached_label(attached) or seat_label(spectating)
    if not expected_label and spectating is False and attached is False:
        expected_label = app_label()

    line = _joined_strip(
        spectating=spectating, attached=attached, liveness_text="x", width=width
    )
    segs = compose_control_strip_segments(
        spectating=spectating, attached=attached, liveness_text="x", width=width
    )

    assert "".join(text for text, _tone in segs) == line  # concatenation invariant, per-case

    if expected_label == MANUAL_LABEL:
        assert line.startswith(MANUAL_LABEL)
    elif expected_label == APP_LABEL:
        assert line.startswith(APP_LABEL)
    elif expected_label == SPECTATE_LABEL:
        assert line.startswith(SPECTATE_LABEL)
    else:
        assert expected_label == ""
        assert MANUAL_LABEL not in line
        assert APP_LABEL not in line
        assert SPECTATE_LABEL not in line

    toned = [seg for seg in segs if seg[1] is not None]
    assert len(toned) <= 1  # XOR: App and MANUAL never co-render

    assert "AI-PILOT" not in line
    assert "AUTO-LOOP" not in line
    assert not any("AI-PILOT" in text or "AUTO-LOOP" in text for text, _tone in segs)


# --- Degrade DIRECTION pin (team-lead-mandated, post-review addendum):
# for EVERY garbage/None/raising input combination, the resolved label
# must NEVER be App -- the 060 sibling of 056's own "an unknown must never
# invent the 'you have control' claim" (_safe_attached's own docstring),
# now also holding for App's own affirmative claim. -------------------------


def test_app_renders_iff_literal_false_on_both_axes_self_contained():
    """The PRIMARY pin for the App-eligibility gate -- deliberately
    SELF-CONTAINED: it hardcodes the expected outcome directly from the raw
    matrix inputs via `is False` identity checks and never imports or calls
    `seat_label`/`attached_label`/`app_label`/`_is_definitively_false` as an
    oracle. The oracle-driven tests elsewhere in this file (e.g. test_
    degrade_matrix_label_matches_priority_oracle_and_never_raises) would
    silently keep agreeing with a future change that loosens the App gate
    AND its own oracle computation together in the same commit -- this test
    can't be fooled that way, because it never reads the gate's own
    implementation at all, only `compose_control_strip_segments`'s/`compose_
    control_strip_segments`'s observable output. Swept across the full
    13x13 degrade matrix (garbage/None/raising included on both axes)."""
    width = 60
    for spectating in _DEGRADE_MATRIX_INPUTS:
        for attached in _DEGRADE_MATRIX_INPUTS:
            expect_app = spectating is False and attached is False

            line = _joined_strip(
                spectating=spectating, attached=attached, liveness_text="x", width=width
            )
            segs = compose_control_strip_segments(
                spectating=spectating, attached=attached, liveness_text="x", width=width
            )

            assert (APP_LABEL in line) == expect_app, (spectating, attached, line)
            app_seg_present = any(APP_LABEL in text for text, _tone in segs)
            assert app_seg_present == expect_app, (spectating, attached, segs)
            ok_tone_present = any(tone == "ok" for _text, tone in segs)
            assert ok_tone_present == expect_app, (spectating, attached, segs)


def test_degrade_direction_never_invents_app_from_unknown_or_garbage_state():
    width = 60
    for spectating in _DEGRADE_MATRIX_INPUTS:
        for attached in _DEGRADE_MATRIX_INPUTS:
            if spectating is False and attached is False:
                continue  # the one legitimate App case -- covered elsewhere
            line = _joined_strip(
                spectating=spectating, attached=attached, liveness_text="x", width=width
            )
            segs = compose_control_strip_segments(
                spectating=spectating, attached=attached, liveness_text="x", width=width
            )
            assert APP_LABEL not in line, (spectating, attached, line)
            assert not any(APP_LABEL in text for text, _tone in segs), (spectating, attached, segs)


def test_both_none_never_renders_app_or_any_other_claim():
    # None cleanly coerces to False for seat_label/attached_label's OWN
    # purposes (their established convention, unchanged by this WO), but
    # is not the literal `False` singleton the App gate requires -- the
    # row must degrade to liveness-only, not invent any of the three chips.
    line = _joined_strip(spectating=None, attached=None, liveness_text="x", width=60)
    assert APP_LABEL not in line
    assert MANUAL_LABEL not in line
    assert SPECTATE_LABEL not in line


@pytest.mark.parametrize("falsy_non_bool", [0, "", [], {}])
def test_falsy_but_non_bool_spectating_never_clears_the_app_bar(falsy_non_bool):
    # 0/""/[]/{} are cleanly falsy for seat_label's own purposes but are
    # NOT the literal `False` singleton -- must not clear the App bar even
    # paired with a genuinely False attached.
    line = _joined_strip(
        spectating=falsy_non_bool, attached=False, liveness_text="x", width=60
    )
    assert APP_LABEL not in line


def test_raising_attached_with_definitively_false_spectating_never_renders_app():
    # The sharpest case: `attached` is unevaluable (raises) and degrades to
    # "not attached" (`_safe_attached`'s own existing, unchanged
    # philosophy) while `spectating` is genuinely, literally False. Before
    # this hardening, both `attached_label`/`seat_label` would evaluate
    # empty and the OLD (ungated) fallback would have invented App here --
    # the gate must suppress it since `attached`'s own truthiness was never
    # actually confirmed.
    line = _joined_strip(
        spectating=False, attached=_HostileBool(), liveness_text="x", width=60
    )
    assert APP_LABEL not in line
    assert MANUAL_LABEL not in line


def test_degrade_matrix_never_raises_at_narrow_and_zero_widths_too():
    # Same matrix, tiny/degenerate widths -- the drop/degrade paths, not
    # just the roomy one the main matrix test above uses.
    for spectating in _DEGRADE_MATRIX_INPUTS:
        for attached in _DEGRADE_MATRIX_INPUTS:
            for width in (0, -1, 1, 2, 3, float("nan"), float("inf"), "nope"):
                line = _joined_strip(
                    spectating=spectating, attached=attached, liveness_text="x", width=width
                )
                segs = compose_control_strip_segments(
                    spectating=spectating, attached=attached, liveness_text="x", width=width
                )
                assert "".join(text for text, _tone in segs) == line


# --- Vocabulary ban, standalone --------------------------------------------


def test_no_retired_vocabulary_anywhere_in_module_constants():
    from tw2002_aiclient.cockpit import control_seat as control_seat_mod

    for name in ("SPECTATE_LABEL", "MANUAL_LABEL", "APP_LABEL"):
        value = getattr(control_seat_mod, name)
        assert "AI-PILOT" not in value
        assert "AUTO-LOOP" not in value
        assert "ai_pilot" not in value
        assert "auto_loop" not in value
