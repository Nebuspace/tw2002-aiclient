"""WO-P5-062 Layer-B -- the ARM indicator's placement in the control strip
(``cockpit.control_seat``) and its wiring through ``screens.
PlayShellScreen.draw()``.

Layer-A (the pure state extraction and label/tone mapping) lives in
``tests/test_cockpit_arm.py``. This file proves the three things a pure
composer test cannot:

  1. **Arm and seat are independent** (Accept #1) -- not merely that both
     render, but that neither input can move the other's output. An armed
     autopilot that does NOT hold the seat is a legitimate state and is
     representable here.
  2. **Arming cannot happen implicitly** (Accept #3) -- the cockpit holds
     no arm state of its own, so there is nothing for any action to flip.
     Proved by driving the paths that could plausibly arm and by pinning
     the chip's only input to the daemon's own reported payload.
  3. The chip reaches a real drawn row without crowding out the liveness
     cluster the strip already carries.

Harness: the headless fake-stdscr idiom every sibling cockpit-panel suite
uses (``tests/test_cockpit_spectate.py``'s ``_RecordingWin``, reused
verbatim by ``tests/test_cockpit_stopbanner_wiring.py``) -- real
``draw()``, real ``frame_layout``, no pty, no daemon, no network. The
real-terminal proof lives in ``tests/test_cockpit_arm_pty.py``.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit import arm as cockpit_arm
from tw2002_aiclient.cockpit import control_seat
from tw2002_aiclient.cockpit.arm import (
    ARM_GAP,
    ARM_OFF_LABEL,
    ARM_ON_LABEL,
    ARM_UNKNOWN_LABEL,
)
from tw2002_aiclient.cockpit.control_seat import (
    APP_LABEL,
    MANUAL_LABEL,
    SPECTATE_LABEL,
    compose_control_strip_line,
    compose_control_strip_segments,
)
from tw2002_aiclient.cockpit.layout import frame_layout

FULL_ROWS, FULL_COLS = 40, 160
HANDLE = "Alpha"

# The three seat states, as the literal ``(spectating, attached)`` pairs
# ``control_seat`` actually gates on -- App-hold requires both to be the
# literal ``False`` singleton (its ``_is_definitively_false`` gate).
_SEATS = {
    APP_LABEL: (False, False),
    MANUAL_LABEL: (False, True),
    SPECTATE_LABEL: (True, False),
}

# The three arm readings, as the status payloads that produce them.
_ARMS = {
    ARM_ON_LABEL: {"autopilot": {"running": True}},
    ARM_OFF_LABEL: {"autopilot": {"running": False}},
    ARM_UNKNOWN_LABEL: {"autopilot": {"running": None}},
}


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


def _screen(monkeypatch, win, status=None, *, spectating=False, attached=False):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.spectating = spectating
    screen.attached = attached
    screen.status_provider = lambda: status
    return screen


def _control_strip_calls(win, rows=FULL_ROWS, cols=FULL_COLS):
    """Every content write on the control-strip row, bounded to that
    region's own column span and sorted left-to-right.

    Bounding BOTH edges is load-bearing (the same trap the sibling wiring
    suites document): the outer double-line frame draws its own border
    cells on this very row at ``x = 0`` and ``x = cols - 1``, and an
    unbounded reader silently returns them as part of the row."""
    region = frame_layout(rows, cols)["control_strip"]
    assert region is not None
    lo, hi = region["x"], region["x"] + region["w"]
    calls = sorted(
        (x, text, attr)
        for (y, x, text, attr) in win.calls
        if y == region["y"] and lo <= x < hi
    )
    assert calls, "expected an addstr call on the control strip row"
    return calls


def _control_strip_text(win, rows=FULL_ROWS, cols=FULL_COLS) -> str:
    return "".join(text for _x, text, _attr in _control_strip_calls(win, rows, cols))


def _drawn_row(monkeypatch, status, *, spectating=False, attached=False) -> str:
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, status, spectating=spectating, attached=attached)
    screen.draw()
    return _control_strip_text(win)


# ---------------------------------------------------------------------------
# 1. ACCEPT #1 -- arm state and seat state are orthogonal.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seat_label", list(_SEATS))
@pytest.mark.parametrize("arm_label_text", list(_ARMS))
def test_every_seat_and_arm_combination_renders_both_chips(
    monkeypatch, seat_label, arm_label_text
):
    """All nine combinations, including the three the WO calls out as the
    point of the whole change: an armed autopilot that does not hold the
    seat. ``ARM ON`` beside ``MANUAL — YOU HAVE CONTROL`` is not a
    contradiction to be suppressed -- it is the honest report that the
    human has the keyboard while a taught behaviour remains armed."""
    spectating, attached = _SEATS[seat_label]
    row = _drawn_row(
        monkeypatch, _ARMS[arm_label_text], spectating=spectating, attached=attached
    )
    assert seat_label in row
    assert arm_label_text in row


def test_the_arm_reading_is_unmoved_by_every_seat_state(monkeypatch):
    """Independence, direction one: hold the daemon's report fixed, walk
    every seat state, and assert the arm text never changes. This is
    stronger than "both render" -- it fails if the seat state is ever
    allowed to leak into the arm decision (e.g. a future "we're attached,
    so surely nothing is armed" shortcut)."""
    for status_label, status in _ARMS.items():
        seen = set()
        for spectating, attached in _SEATS.values():
            row = _drawn_row(monkeypatch, status, spectating=spectating, attached=attached)
            seen.add(next(a for a in _ARMS if a in row))
        assert seen == {status_label}, (
            f"arm reading moved with the seat state: {seen}"
        )


def test_the_seat_reading_is_unmoved_by_every_arm_state(monkeypatch):
    """Independence, direction two -- the mirror, which matters just as
    much: arming must never appear to change who holds the keyboard.
    That is this WO's stated hazard (ARM != take the human lock) observed
    at the surface the operator actually reads."""
    for seat_label, (spectating, attached) in _SEATS.items():
        seen = set()
        for status in _ARMS.values():
            row = _drawn_row(monkeypatch, status, spectating=spectating, attached=attached)
            seen.add(next(s for s in _SEATS if s in row))
        assert seen == {seat_label}, f"seat reading moved with the arm state: {seen}"


def test_arm_reads_a_different_input_than_the_seat_badge_entirely(monkeypatch):
    """The structural root of the independence above: the seat badge is
    composed from this client's own two booleans and never sees the status
    payload, while the arm chip is composed from the status payload and
    never sees the booleans. Proved by handing the seat composer a status
    dict's worth of nonsense and the arm composer a seat's worth -- neither
    can act on the other's vocabulary."""
    # Seat composer, given only arm vocabulary: no arm chip appears.
    seat_only = compose_control_strip_line(
        spectating=False, attached=False, liveness_text="", width=60
    )
    assert APP_LABEL in seat_only
    for arm_text in _ARMS:
        assert arm_text not in seat_only
    # Arm composer, given seat booleans as its payload: no seat label, and
    # no arm claim invented from them either.
    assert cockpit_arm.compose_arm_chip({"spectating": False, "attached": True}) == (
        ARM_UNKNOWN_LABEL,
        "warn",
    )


def test_lock_state_words_never_appear_in_any_arm_label():
    """ARM != take the human lock, pinned at the vocabulary level. If a
    future edit reached for ``ARM -> HUMAN`` or ``ARM (LOCKED)`` the chip
    would start implying a lock transition it does not perform, and this
    fails before it ships."""
    for label in (ARM_ON_LABEL, ARM_OFF_LABEL, ARM_UNKNOWN_LABEL):
        upper = label.upper()
        for banned in ("LOCK", "HUMAN", "MANUAL", "ATTACH", "SPECTATE", "CONTROL"):
            assert banned not in upper, f"{label!r} implies a seat/lock change"


# ---------------------------------------------------------------------------
# 2. ACCEPT #3 -- NO SILENT ARM.
# ---------------------------------------------------------------------------

# Every key the cockpit could plausibly route, including the Mode chord,
# the detach chord, the reserved teach triad, and ordinary navigation.
_PLAUSIBLE_KEYS = [
    screens_mod.MODE_KEY,        # Ctrl-A -- the App<->Human Mode chord
    29,                          # Ctrl-] -- detach
    ord("M"), ord("m"),          # TW Move (and the retired Mode draft)
    ord("A"), ord("R"), ord("T"),  # the reserved teach triad
    ord("a"), ord("r"), ord("t"),
    ord("y"), ord("Y"), ord("n"), ord("N"),  # a confirm-gate's own keys
    ord("\n"), ord(" "), 27, ord("q"), ord("Q"),
    curses.KEY_UP, curses.KEY_DOWN, curses.KEY_ENTER, curses.KEY_RESIZE,
]


def test_no_key_and_no_seat_transition_can_make_the_indicator_read_armed(monkeypatch):
    """Accept #3, behaviourally. The daemon reports a disarmed autopilot
    throughout. Every plausible key is routed, every seat transition
    ``app.py::_run_play`` performs is applied by hand, and the strip is
    redrawn after each -- ``ARM ON`` must never appear on any frame."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, {"autopilot": {"running": False}})

    for spectating, attached in ((False, False), (False, True), (True, False)):
        screen.spectating, screen.attached = spectating, attached
        for key in _PLAUSIBLE_KEYS:
            screen.handle_key(key)
            win.calls.clear()
            screen.draw()
            row = _control_strip_text(win)
            assert ARM_ON_LABEL not in row, (
                f"key {key!r} at seat ({spectating}, {attached}) produced an ARM ON claim"
            )
            assert ARM_OFF_LABEL in row


def test_that_assertion_is_not_vacuous_only_the_daemons_report_can_arm(monkeypatch):
    """The companion without which the test above proves nothing.

    Identical drive, identical keys, identical seat transitions -- the ONE
    thing changed is the daemon's own reported payload, and now ``ARM ON``
    appears on every frame. So the absence above is a real property of the
    cockpit, not an artefact of a chip that simply never says ``ARM ON``."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, {"autopilot": {"running": True}})

    for spectating, attached in ((False, False), (False, True), (True, False)):
        screen.spectating, screen.attached = spectating, attached
        for key in _PLAUSIBLE_KEYS:
            screen.handle_key(key)
            win.calls.clear()
            screen.draw()
            assert ARM_ON_LABEL in _control_strip_text(win)


def test_the_chip_only_ever_sees_the_object_the_status_provider_returned(monkeypatch):
    """The structural half of Accept #3: the cockpit cannot fabricate an
    arm input, because the only value that ever reaches ``compose_arm_
    chip`` is -- by identity, not by equality -- the exact object the
    daemon poll handed back. A locally-synthesised or locally-amended
    payload would be a different object and would fail here."""
    payload = {"autopilot": {"running": False}}
    seen: list[object] = []
    real = cockpit_arm.compose_arm_chip

    def _spy(status):
        seen.append(status)
        return real(status)

    monkeypatch.setattr(screens_mod.cockpit_arm, "compose_arm_chip", _spy)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, payload)
    for key in _PLAUSIBLE_KEYS:
        screen.handle_key(key)
        screen.draw()

    assert seen, "compose_arm_chip was never reached -- this test proves nothing"
    for status in seen:
        assert status is payload


def test_the_cockpit_holds_no_arm_state_of_its_own(monkeypatch):
    """There is nothing to flip. ``PlayShellScreen`` carries booleans for
    the seat (``spectating``/``attached``) because those really are this
    client's own facts; the arm state is the daemon's fact and is
    deliberately not mirrored here. An attribute that cached it would be a
    place a side effect could write, which is exactly the failure mode
    this Accept forbids."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, {"autopilot": {"running": False}})
    screen.draw()
    offenders = [
        name for name in vars(screen)
        if "arm" in name.lower() and "warn" not in name.lower()
    ]
    assert not offenders, f"cockpit is caching arm state in {offenders}"


def test_a_dropped_status_poll_degrades_to_unknown_never_to_a_calm_disarmed(monkeypatch):
    """The failure mode with real consequences: the daemon goes away
    mid-session. The chip must stop claiming ``ARM OFF`` the moment it
    stops having evidence for it -- an operator must not read a stale calm
    as a live one."""
    for status in (None, {}, {"ok": False}, {"autopilot": {}}):
        row = _drawn_row(monkeypatch, status)
        assert ARM_UNKNOWN_LABEL in row
        assert ARM_OFF_LABEL not in row
        assert ARM_ON_LABEL not in row


def test_a_raising_status_provider_shows_unknown_rather_than_a_calm_claim(monkeypatch):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(win, profile)

    def _boom():
        raise RuntimeError("provider exploded")

    screen.status_provider = _boom
    screen.draw()
    assert ARM_UNKNOWN_LABEL in _control_strip_text(win)


# ---------------------------------------------------------------------------
# 3. Draw wiring -- the chip reaches the row, styled, without crowding out
#    the liveness cluster.
# ---------------------------------------------------------------------------


def test_the_arm_chip_lands_immediately_right_of_the_seat_chip(monkeypatch):
    row = _drawn_row(monkeypatch, _ARMS[ARM_ON_LABEL])
    assert row.startswith(APP_LABEL + ARM_GAP + ARM_ON_LABEL)


def test_the_liveness_cluster_still_survives_beside_both_chips(monkeypatch):
    """The strip's pre-existing, operationally load-bearing "is it
    frozen?" signal keeps its full space -- the new chip is secondary
    content and must never be the reason it is lost."""
    for status in _ARMS.values():
        row = _drawn_row(monkeypatch, status)
        assert "→" in row


def test_the_armed_chip_carries_the_badge_attributes(monkeypatch):
    """Canon's badge law (``mode-line-and-teach-controls.md`` ~179-181):
    reverse-video is the single "selected/active/badge" signal. Colours
    are off in this harness, so the honest remainder of the warn tone is
    A_BOLD -- the chip is still a chip without colour."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _ARMS[ARM_ON_LABEL])
    screen.draw()
    attrs = [attr for _x, text, attr in _control_strip_calls(win) if ARM_ON_LABEL in text]
    assert attrs, "the ARM ON chip was not drawn as its own segment"
    for attr in attrs:
        assert attr & curses.A_REVERSE
        assert attr & curses.A_BOLD


def test_the_disarmed_chip_stays_calm_and_unbadged(monkeypatch):
    """The muted register ``SPECTATE`` already establishes on this row:
    a proven-disarmed autopilot is the "nothing to see here" state and
    must not compete for attention with the seat chip beside it."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _ARMS[ARM_OFF_LABEL])
    screen.draw()
    attrs = [attr for _x, text, attr in _control_strip_calls(win) if ARM_OFF_LABEL in text]
    assert attrs
    for attr in attrs:
        assert not attr & curses.A_REVERSE


def test_a_raising_arm_composer_never_crashes_the_draw_pass(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("arm composer exploded")

    monkeypatch.setattr(screens_mod.cockpit_arm, "compose_arm_chip", _boom)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _ARMS[ARM_ON_LABEL])
    screen.draw()  # must not raise
    row = _control_strip_text(win)
    assert APP_LABEL in row  # the seat chip and the rest of the row survive
    assert "→" in row


# ---------------------------------------------------------------------------
# 4. The composer's placement contract, at the pure layer.
# ---------------------------------------------------------------------------


def _chip(text, tone=None):
    return (text, tone)


def test_omitting_the_arm_chip_is_byte_identical_to_the_pre_wo_row():
    """Backward compatibility, structurally: with no arm chip supplied the
    composer must produce exactly the row it produced before this WO. The
    reference is not a hand-typed twin -- it is the same function with the
    parameter left at its default, which is what every pre-WO caller
    passes."""
    for spectating, attached in _SEATS.values():
        for width in (20, 40, 60, 82, 158):
            base = compose_control_strip_segments(
                spectating=spectating, attached=attached,
                liveness_text="● ⠋ → -", width=width,
            )
            explicit_none = compose_control_strip_segments(
                spectating=spectating, attached=attached,
                liveness_text="● ⠋ → -", width=width, arm_chip=None,
            )
            assert base == explicit_none


def test_the_row_is_still_exactly_width_characters_with_the_arm_chip_present():
    """The invariant every caller of this row depends on. A chip that
    pushed the row wider would run past the frame's own border cell."""
    for width in range(1, 120):
        segments = compose_control_strip_segments(
            spectating=False, attached=False, liveness_text="● ⠋ → 158",
            width=width, arm_chip=_chip(ARM_ON_LABEL, "warn"),
        )
        assert sum(len(text) for text, _tone in segments) == width


def test_line_and_segments_stay_byte_identical_with_an_arm_chip():
    """The concatenation invariant PWO-060 established, extended to the
    new parameter -- both public composers still route through the one
    shared helper, so they cannot drift."""
    for spectating, attached in _SEATS.values():
        for arm in (None, _chip(ARM_ON_LABEL, "warn"), _chip(ARM_OFF_LABEL), _chip("?")):
            for width in (0, 1, 8, 25, 33, 40, 82, 158):
                kwargs = dict(
                    spectating=spectating, attached=attached,
                    liveness_text="● ⠋ → 158", width=width, arm_chip=arm,
                )
                line = compose_control_strip_line(**kwargs)
                segments = compose_control_strip_segments(**kwargs)
                assert line == "".join(text for text, _tone in segments)


def test_the_arm_chip_is_all_or_nothing_never_truncated():
    """The width-pressure safety property. A partially-rendered ``ARM ON``
    could read as ``ARM O``, ``ARM``, or ``AR`` -- each of which an
    operator could resolve the wrong way. The chip either fits whole or
    yields entirely, and yielding is honest (absence of information)
    where truncation would not be (wrong information).

    Swept across every width from nothing to roomy, at every seat state,
    so the boundary itself is covered rather than two chosen points.

    Read on SEGMENTS, not on the flat line, and that is not a stylistic
    choice. The seat label truncates by design (``APP`` legitimately
    renders as ``A`` at a squeezed width -- pre-existing PWO-055/060
    behaviour, unchanged by this WO), and ``"A"`` is also a prefix of
    ``ARM ON``, so a flat-string prefix scan reports a partial arm chip
    that was never there. Segments carry the boundary the flat string
    loses: the seat's own segment is identifiable and excluded, and every
    remaining segment is then held to the all-or-nothing rule."""
    for seat_label, (spectating, attached) in _SEATS.items():
        for width in range(0, 130):
            segments = compose_control_strip_segments(
                spectating=spectating, attached=attached, liveness_text="● ⠋ → 158",
                width=width, arm_chip=_chip(ARM_ON_LABEL, "warn"),
            )
            texts = [text for text, _tone in segments]
            # Drop at most one leading seat segment (whole or truncated).
            if texts and texts[0] and seat_label.startswith(texts[0]):
                texts = texts[1:]
            for text in texts:
                if not text or text == ARM_ON_LABEL:
                    continue
                assert not ARM_ON_LABEL.startswith(text), (
                    f"width {width} at seat {seat_label!r} rendered a partial "
                    f"ARM chip: {text!r} (segments {segments!r})"
                )


def test_the_seat_chip_outranks_the_arm_chip_under_width_pressure():
    """Canon (``mode-line-and-teach-controls.md`` ~223): "the mode chip is
    cell #1, hard-left -- *who holds the keyboard* is the highest-priority
    fact on the strip." So when only one chip fits, it is the seat's.
    Stated here rather than left implicit, because the opposite ordering
    is a defensible-sounding choice someone could make later by accident."""
    width = len(MANUAL_LABEL) + len("● ⠋ → 158") + 1
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="● ⠋ → 158",
        width=width, arm_chip=_chip(ARM_ON_LABEL, "warn"),
    )
    assert MANUAL_LABEL in line
    assert ARM_ON_LABEL not in line


def test_the_arm_chip_renders_even_when_the_seat_makes_no_claim():
    """Independence at the composer layer, in the case that would be
    easiest to get wrong: when both seat booleans are ambiguous the seat
    label is deliberately empty (``control_seat`` refuses to invent a
    claim). The arm chip must still render -- it is answering a different
    question and its own evidence is unaffected."""
    line = compose_control_strip_line(
        spectating=None, attached=None, liveness_text="→ -", width=60,
        arm_chip=_chip(ARM_ON_LABEL, "warn"),
    )
    assert line.startswith(ARM_ON_LABEL)
    for seat in _SEATS:
        assert seat not in line


@pytest.mark.parametrize("arm_chip", [
    "ARM ON", 42, object(), (), ("only-one",), ("a", "b", "c"),
    (object(), "warn"), (ARM_ON_LABEL, object()), [ARM_ON_LABEL, "warn"],
])
def test_a_malformed_arm_chip_degrades_to_no_chip_and_never_raises(arm_chip):
    """House hardening discipline: every public composer here is
    never-raises regardless of input shape. An unusable chip drops rather
    than rendering a mangled claim."""
    line = compose_control_strip_line(
        spectating=False, attached=False, liveness_text="→ -", width=60,
        arm_chip=arm_chip,
    )
    assert len(line) == 60
    assert line.startswith(APP_LABEL)


def test_an_unknown_arm_tone_degrades_to_plain_rather_than_dropping_the_chip(monkeypatch):
    """A tone outside the draw layer's vocabulary must not cost the
    operator the chip itself -- the text is the load-bearing part, the
    tone is emphasis."""
    segments = compose_control_strip_segments(
        spectating=False, attached=False, liveness_text="→ -", width=60,
        arm_chip=(ARM_ON_LABEL, "chartreuse"),
    )
    assert any(text == ARM_ON_LABEL for text, _tone in segments)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _ARMS[ARM_OFF_LABEL])
    assert screen._control_strip_segment_attr("chartreuse") == curses.A_NORMAL


def test_exactly_one_status_poll_per_draw_with_the_arm_chip_wired(monkeypatch):
    """The arm chip is a new consumer of the shared per-draw snapshot; it
    must not become a second poll. (The poll guard itself needed no new
    term -- ``regions["control_strip"] is not None`` is already one of its
    four, and the chip only ever renders inside that same region -- but
    "needed no change" is worth executing rather than asserting.)"""
    count: list[int] = []
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(win, profile)

    def _provider():
        count.append(1)
        return {"autopilot": {"running": True}}

    screen.status_provider = _provider
    screen.draw()
    assert len(count) == 1
    count.clear()
    screen.draw()
    assert len(count) == 1


def test_control_seat_still_never_reads_the_daemon_status_itself():
    """``control_seat``'s module docstring commits at length to never
    sourcing its chip from the daemon-global status payload -- that
    discipline is exactly why this WO hands it a pre-resolved ``(text,
    tone)`` pair rather than the payload. Pinned so a later convenience
    refactor cannot quietly move the status read into the seat composer.

    Scanned over the AST with docstrings excluded by node identity (the
    technique ``tests/test_mode_badge_vocabulary.py`` establishes), not
    over raw source: both this module and the arm module discuss the
    status payload by name in their prose, and a text scan would either
    false-positive on that or have to be loosened until it proved
    nothing."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(control_seat))
    docstrings = set()
    for scope in ast.walk(tree):
        if isinstance(scope, (ast.Module, ast.ClassDef, ast.FunctionDef)) and scope.body:
            first = scope.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            assert "autopilot" not in node.value, (
                f"control_seat reads the daemon payload directly: {node.value!r}"
            )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
            for name in names:
                assert "session" not in name, f"control_seat imported {name!r}"
