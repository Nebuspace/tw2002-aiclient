"""WO-P5-062 Layer-B, revised by WO-PLAY-STRIP-TRAINER-CHROME -- the ARM
indicator's placement in the control strip (``cockpit.control_seat``) and
its wiring through ``screens.PlayShellScreen.draw()``.

DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 1 retires the
separate, daemon-sourced ARM chip from THIS product's draw wiring: the
merged seat chip (`^A)APP-ARMED`/`^A)MANUAL-HUMAN`, via
`compose_control_strip_segments(..., trainer_labels=True)`) replaces it.
`cockpit/arm.py` and `cockpit_arm.compose_arm_chip` are UNCHANGED and still
exist as a pure composer (Layer-A: ``tests/test_cockpit_arm.py``) -- only
``screens.py`` no longer calls them. This file now proves:

  1. **The merged seat chip renders correctly for all three seat states**,
     and never depends on the daemon's ``status["autopilot"]`` payload --
     the trainer's "App holding the seat" == "armed" reading is a purely
     LOCAL, client-side fact (DECISION point 6), not a second daemon-
     verified claim the way the retired ARM chip was.
  2. **SPECTATE never lies APP-ARMED** (DECISION point 1's explicit
     honesty carve-out) -- no key, seat transition, or daemon payload can
     make a spectating instance claim an armed/manual seat.
  3. **No separate ARM chip ever reaches the drawn row** -- none of
     ``ARM_ON_LABEL``/``ARM_OFF_LABEL``/``ARM_UNKNOWN_LABEL`` appear on the
     control strip regardless of the daemon's reported autopilot state.
  4. The merged chip reaches a real drawn row, styled, without crowding
     out the liveness cluster the strip already carries.
  5. The PURE composer layer (``compose_control_strip_segments``'s own
     ``arm_chip`` parameter) is untouched and still supports a non-trainer
     caller supplying an arm chip explicitly -- proven in section 4 below,
     unchanged by this WO.

Harness: the headless fake-stdscr idiom every sibling cockpit-panel suite
uses (``tests/test_cockpit_spectate.py``'s ``_RecordingWin``, reused
verbatim by ``tests/test_cockpit_stopbanner_wiring.py``) -- real
``draw()``, real ``frame_layout``, no pty, no daemon, no network.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit import arm as cockpit_arm
from tw2002_aiclient.cockpit import control_seat
from tw2002_aiclient.cockpit.arm import (
    ARM_OFF_LABEL,
    ARM_ON_LABEL,
    ARM_UNKNOWN_LABEL,
)
from tw2002_aiclient.cockpit.control_seat import (
    APP_LABEL,
    MANUAL_LABEL,
    SPECTATE_LABEL,
    TRAINER_APP_ARMED_LABEL,
    TRAINER_APP_ARMED_LABEL_NARROW,
    TRAINER_MANUAL_HUMAN_LABEL,
    TRAINER_MANUAL_HUMAN_LABEL_NARROW,
    compose_control_strip_segments,
)

def _joined_strip(**kwargs) -> str:
    """Flat join of ``compose_control_strip_segments`` — test-only stand-in
    for the retired product flat-string strip helper."""
    return "".join(text for text, _tone in compose_control_strip_segments(**kwargs))

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

# Three distinct daemon status payloads that the retired ARM chip used to
# read (`ARM ON`/`ARM OFF`/`ARM ?`). Kept under these names purely as three
# VARIED status fixtures for the "the merged seat label never depends on
# this payload" tests below -- `screens.py`'s draw() no longer reads
# ``status["autopilot"]`` for anything, so no chip keyed to these labels
# ever reaches the row any more (see section 2/3 below).
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
# 1. Merged trainer seat chip -- correct per seat state, and never moved by
#    the retired ARM chip's would-be input (the daemon autopilot payload).
# ---------------------------------------------------------------------------

_TRAINER_MERGED = {
    APP_LABEL: TRAINER_APP_ARMED_LABEL,
    MANUAL_LABEL: TRAINER_MANUAL_HUMAN_LABEL,
    SPECTATE_LABEL: SPECTATE_LABEL,
}


@pytest.mark.parametrize("seat_label", list(_SEATS))
@pytest.mark.parametrize("arm_label_text", list(_ARMS))
def test_every_seat_state_renders_its_merged_trainer_label_regardless_of_daemon_arm(
    monkeypatch, seat_label, arm_label_text
):
    """The merged-chip replacement for the retired ARM-chip Accept #1: the
    trainer's seat+armed chip is a purely LOCAL reading (DECISION point 6)
    and must render identically no matter what the daemon reports for
    ``autopilot`` -- there is no longer a second, daemon-sourced claim on
    this row for a seat transition to leak into or out of."""
    spectating, attached = _SEATS[seat_label]
    row = _drawn_row(
        monkeypatch, _ARMS[arm_label_text], spectating=spectating, attached=attached
    )
    assert _TRAINER_MERGED[seat_label] in row


def test_the_merged_label_is_unmoved_by_every_daemon_arm_state(monkeypatch):
    """Independence, direction one, restated for the merged chip: hold the
    seat fixed, walk every daemon ``autopilot`` payload the retired ARM
    chip used to read, and assert the merged label text never changes."""
    for seat_label, (spectating, attached) in _SEATS.items():
        seen = set()
        for status in _ARMS.values():
            row = _drawn_row(monkeypatch, status, spectating=spectating, attached=attached)
            seen.add(_TRAINER_MERGED[seat_label] in row)
        assert seen == {True}, (
            f"merged label for {seat_label!r} moved with the daemon arm payload"
        )


def test_spectate_never_lies_an_armed_or_manual_seat(monkeypatch):
    """DECISION point 1's explicit honesty carve-out: SPECTATE must never
    render either merged claim (``-ARMED`` or ``-HUMAN``), no matter what
    the daemon reports. A spectating instance holds no seat and must not
    be caught implying otherwise."""
    for status in _ARMS.values():
        row = _drawn_row(monkeypatch, status, spectating=True, attached=False)
        assert SPECTATE_LABEL in row
        assert TRAINER_APP_ARMED_LABEL not in row
        assert TRAINER_APP_ARMED_LABEL_NARROW not in row
        assert TRAINER_MANUAL_HUMAN_LABEL not in row
        assert TRAINER_MANUAL_HUMAN_LABEL_NARROW not in row


def test_arm_reads_a_different_input_than_the_seat_badge_entirely(monkeypatch):
    """The structural root of the independence above: the seat badge is
    composed from this client's own two booleans and never sees the status
    payload, while the arm chip is composed from the status payload and
    never sees the booleans. Proved by handing the seat composer a status
    dict's worth of nonsense and the arm composer a seat's worth -- neither
    can act on the other's vocabulary."""
    # Seat composer, given only arm vocabulary: no arm chip appears.
    seat_only = _joined_strip(
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


def test_no_key_and_no_seat_transition_can_make_a_spectating_seat_read_armed(monkeypatch):
    """Accept #3/DECISION point 1, behaviourally, for the merged chip. The
    daemon reports an ``autopilot.running: True`` payload throughout --
    the single input that would have driven the retired ARM chip to
    ``ARM ON`` on every frame. Every plausible key is routed and the strip
    is redrawn after each: a spectating seat must never once claim
    ``-ARMED``/``-HUMAN``, and an App/Manual seat's merged label must never
    move off its own honest reading because of this key or payload."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, {"autopilot": {"running": True}})

    for spectating, attached in ((False, False), (False, True), (True, False)):
        screen.spectating, screen.attached = spectating, attached
        seat_label = next(s for s, pair in _SEATS.items() if pair == (spectating, attached))
        for key in _PLAUSIBLE_KEYS:
            screen.handle_key(key)
            win.calls.clear()
            screen.draw()
            row = _control_strip_text(win)
            if seat_label == SPECTATE_LABEL:
                assert TRAINER_APP_ARMED_LABEL not in row
                assert TRAINER_APP_ARMED_LABEL_NARROW not in row
                assert TRAINER_MANUAL_HUMAN_LABEL not in row
                assert TRAINER_MANUAL_HUMAN_LABEL_NARROW not in row
            else:
                assert _TRAINER_MERGED[seat_label] in row, (
                    f"key {key!r} at seat {seat_label!r} moved the merged label"
                )


def test_no_arm_chip_related_call_reaches_the_retired_composer(monkeypatch):
    """The structural half of Accept #3, restated: ``screens.py`` no
    longer imports or calls ``cockpit_arm.compose_arm_chip`` at all, so
    there is nothing left for a key or seat transition to route into it.
    Proved by spying on the composer itself (still reachable via
    ``cockpit_arm`` directly, since the module is unchanged) and driving
    every plausible key through a full draw pass -- the spy must never
    fire."""
    seen: list[object] = []
    real = cockpit_arm.compose_arm_chip

    def _spy(status):
        seen.append(status)
        return real(status)

    monkeypatch.setattr(cockpit_arm, "compose_arm_chip", _spy)
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, {"autopilot": {"running": False}})
    for key in _PLAUSIBLE_KEYS:
        screen.handle_key(key)
        screen.draw()

    assert not seen, (
        "screens.py's draw() reached the retired cockpit_arm.compose_arm_chip "
        f"composer: {seen!r}"
    )


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
    # WO-P5-063 exemption, by EXACT name and justified below rather than by
    # widening the substring rule.
    #
    # `_arm_confirm` holds the pending confirm-to-arm PROMPT -- `(action,
    # cycles)` or `None` -- i.e. "is a question currently on screen". It is
    # this client's own fact, like `spectating`/`attached` in the docstring
    # above, and it never holds or mirrors the daemon's arm reading: the chip
    # still derives from `status["autopilot"]` alone.
    #
    # The detector here is a name-substring match, so it fires on the letters
    # "arm" rather than on the property the docstring describes. Exempting by
    # name alone would leave that gap papered over, so the exemption is PROVEN
    # rather than asserted: `test_arm_confirm_state_cannot_move_the_arm_chip`
    # in `tests/test_cockpit_armconfirm.py` drives `_arm_confirm` through
    # every value and shows the rendered chip does not move. If a future
    # attribute really does cache the daemon's fact, this list does not cover
    # it and the pin still bites.
    _ARM_CONFIRM_EXEMPT = {"_arm_confirm"}
    offenders = [
        name for name in vars(screen)
        if "arm" in name.lower()
        and "warn" not in name.lower()
        and name not in _ARM_CONFIRM_EXEMPT
    ]
    assert not offenders, f"cockpit is caching arm state in {offenders}"


def test_a_dropped_status_poll_does_not_disturb_the_local_merged_label(monkeypatch):
    """The failure mode the retired ARM chip existed to guard against (the
    daemon going away mid-session) no longer has a daemon-sourced claim on
    this row to degrade at all: the merged label is documented, local
    chrome (DECISION point 6 -- ``screens.py``'s ``__init__`` comment), so
    a dropped/malformed poll must not crash the draw and must leave the
    default App seat's ``-ARMED`` reading exactly where it was."""
    for status in (None, {}, {"ok": False}, {"autopilot": {}}):
        row = _drawn_row(monkeypatch, status)  # default seat = App (False, False)
        assert TRAINER_APP_ARMED_LABEL in row


def test_a_raising_status_provider_does_not_crash_the_draw_pass(monkeypatch):
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(win, profile)

    def _boom():
        raise RuntimeError("provider exploded")

    screen.status_provider = _boom
    screen.draw()  # must not raise
    assert TRAINER_APP_ARMED_LABEL in _control_strip_text(win)


# ---------------------------------------------------------------------------
# 3. Draw wiring -- the chip reaches the row, styled, without crowding out
#    the liveness cluster.
# ---------------------------------------------------------------------------


def test_the_merged_seat_chip_lands_hard_left_with_no_arm_chip_anywhere_on_the_row(
    monkeypatch,
):
    """Canon's cell-#1 priority (``mode-line-and-teach-controls.md``
    ~223) still holds, and DECISION point 1 additionally forbids a
    second, separate ARM chip beside it -- the merged label is now the
    entire hard-left claim, and none of the retired chip's own text
    (``ARM ON``/``ARM OFF``/``ARM ?``) appears anywhere on the row."""
    row = _drawn_row(monkeypatch, _ARMS[ARM_ON_LABEL])
    assert row.startswith(TRAINER_APP_ARMED_LABEL)
    for arm_text in _ARMS:
        assert arm_text not in row


def test_the_liveness_cluster_still_survives_beside_the_merged_chip(monkeypatch):
    """The strip's pre-existing, operationally load-bearing "is it
    frozen?" signal keeps its full space -- the merged seat chip is not
    the reason it would ever be lost."""
    for status in _ARMS.values():
        row = _drawn_row(monkeypatch, status)
        assert "→" in row


def test_the_merged_armed_seat_chip_carries_the_badge_attributes(monkeypatch):
    """Canon's badge law (``mode-line-and-teach-controls.md`` ~179-181):
    reverse-video is the single "selected/active/badge" signal, applied
    to the App seat's ``ok`` tone whether or not this WO's trainer label
    remap is in effect -- the remap only ever changes the label text
    (``_trainer_seat_label``), never the tone it carries."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _ARMS[ARM_ON_LABEL])
    screen.draw()
    attrs = [
        attr for _x, text, attr in _control_strip_calls(win)
        if TRAINER_APP_ARMED_LABEL in text
    ]
    assert attrs, "the merged App-armed chip was not drawn as its own segment"
    for attr in attrs:
        assert attr & curses.A_REVERSE
        assert attr & curses.A_BOLD


def test_the_spectate_chip_stays_calm_and_unbadged(monkeypatch):
    """The muted register ``SPECTATE`` already establishes on this row
    stays muted under the trainer remap too -- ``_trainer_seat_label``
    only remaps ``APP_LABEL``/``MANUAL_LABEL``, never ``SPECTATE_LABEL``,
    so a spectating instance is never dressed up as a badge."""
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = _screen(monkeypatch, win, _ARMS[ARM_OFF_LABEL], spectating=True, attached=False)
    screen.draw()
    attrs = [
        attr for _x, text, attr in _control_strip_calls(win) if SPECTATE_LABEL in text
    ]
    assert attrs
    for attr in attrs:
        assert not attr & curses.A_REVERSE


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
                line = _joined_strip(**kwargs)
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
    line = _joined_strip(
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
    line = _joined_strip(
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
    line = _joined_strip(
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
