"""Loop player (WO-P2-G4-X3) -- the component that actually presses keys.

Everything this suite asserts serves one of three claims, and the first is
the reason the other two are worth having.

1. **A refusal is proven by ZERO BYTES, not by a reason string.** Nearly
   every refusal below is exercised against :class:`NoSendSession`, whose
   ``send_and_confirm`` RAISES. A player that sent first and reported the
   refusal afterwards would satisfy a test that only read
   ``result.reason``, and would still have pressed a key into a screen it
   did not recognize. The raising port is what makes the difference
   visible, and the counter in ``result.sends_issued`` is a second,
   independent witness of the same fact.

2. **The anchor trichotomy is never collapsed.** X1 answers ``read`` /
   ``absent`` / ``unreadable`` and a macro's anchor is an int or ``None``.
   Canon gives a force path to exactly one of those four facts. The grid
   below runs every cell under both ``force`` values and pins that force
   changes exactly one of them -- because "absent" reading as "nothing to
   check" is precisely how a replay runs from the wrong sector.

3. **``money_prompt`` is refused before every send, every cycle.** Not at
   entry only, not after the send, and not with an escape hatch.

The screen fixtures are real captured shapes (X1's own prompt-line
spellings and ``test_classify``'s real StarDock capture), and
``test_the_fixtures_classify_as_this_file_assumes`` re-derives every
classification from the live code rather than trusting the comments -- a
fixture that silently stopped being a ``money_prompt`` would otherwise turn
the safety tests below into ceremony.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from tw2002_aiclient.loops import player as player_mod
from tw2002_aiclient.loops.loader import Loop, LoopStep, load_loop
from tw2002_aiclient.loops.player import (
    FORCEABLE_HALTS,
    HALT_CONFIRM_FAILED,
    HALT_CURRENT_SECTOR_ABSENT,
    HALT_CURRENT_SECTOR_UNREADABLE,
    HALT_FENCED,
    HALT_NEVER_AUTO_ACTION,
    HALT_POST_CLASS,
    HALT_REASONS,
    HALT_SCREEN_UNREADABLE,
    HALT_SETTLE_FAILED,
    HALT_START_ANCHOR_MISMATCH,
    HALT_START_ANCHOR_MISSING,
    HALT_UNRECOGNIZED_SCREEN,
    OUTCOME_COMPLETED,
    OUTCOME_HALTED,
    ReplayResult,
    StepTrace,
    replay_loop,
)
from tw2002_aiclient.session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from tw2002_aiclient.session.state_parser import read_current_sector

# ONE scanner, shared with the loader's own structural pins rather than
# forked -- the same disclosed-coupling call `loader.py` made for
# `store._read_document`. A second copy is how the two pins drift.
from .test_loop_loader import _SEND_SYMBOLS, _send_violations

PKG_ROOT = Path(player_mod.__file__).resolve().parent.parent
PLAYER_SRC = (PKG_ROOT / "loops" / "player.py").read_text(encoding="utf-8")

# The two `session/` modules `player.py` is allowed to import, and the only
# two: closed vocabularies canon requires it to DERIVE rather than restate.
ALLOWED_SESSION_MODULES = frozenset({"classify", "state_parser"})


# --------------------------------------------------------------------------
# Screen fixtures -- real captured shapes
# --------------------------------------------------------------------------

_SECTOR_BODY = (
    "Sector  : 158 in uncharted space.\n"
    "Ports   : Aegis, Class 1 (BBS)\n"
    "Warps to Sector(s) :  231 - 4309\n"
    "\n"
)

# X1's own `LIVE_PROMPT` spelling, with the sector varied.
PROMPT_158 = "Command [TL=00:00:00]:[158] (?=Help)? :"
PROMPT_231 = "Command [TL=00:00:00]:[231] (?=Help)? :"
# X1's `CLASSIC_PROMPT`: a real TWGS shape that carries no sector bracket
# at all, so the current sector is genuinely ABSENT rather than unreadable.
PROMPT_CLASSIC = "Command [TL=00753:0/0/0/850] (?=Help)? :"
# A bracket opened and never resolved -- what a poll landing mid-paint sees.
PROMPT_DAMAGED = "Command [TL=00:00:00]:["

# `test_classify`'s real StarDock capture prompt (DECISIONS §A.2).
PROMPT_HOLDS = "How many holds would you like to buy [0-20] ?"
_HOLDS_BODY = (
    "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
    "Your ship can hold up to 20 additional cargo holds.\n"
    "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
)

_PORT_BODY = "Docking...\n\nCommerce report for Aegis: 1 Fuel Ore, Organics, Equipment\n\n"
PROMPT_PORT = "<Trade with this port> (Y/N)? "

_ODD_BODY = "The Ferrengi ambassador stares at you in silence.\n"
PROMPT_ODD = "Well? "


def _screen(body: str, prompt: str) -> tuple[str, str]:
    return body + prompt, prompt


ANCHOR_158 = _screen(_SECTOR_BODY, PROMPT_158)          # main_command, sector 158
ANCHOR_231 = _screen(_SECTOR_BODY, PROMPT_231)          # main_command, sector 231
CLASSIC = _screen(_SECTOR_BODY, PROMPT_CLASSIC)         # main_command, sector absent
DAMAGED = _screen(_SECTOR_BODY, PROMPT_DAMAGED)         # main_command, sector unreadable
MONEY = _screen(_HOLDS_BODY, PROMPT_HOLDS)              # money_prompt
PORT = _screen(_PORT_BODY, PROMPT_PORT)                 # port_trade
ODD = _screen(_ODD_BODY, PROMPT_ODD)                    # unknown


def test_the_fixtures_classify_as_this_file_assumes():
    """Re-derived from the live code, never trusted from a comment.

    Every safety assertion below is only as good as its fixture: a
    ``money_prompt`` that quietly stopped classifying as one would leave
    the never-auto tests passing while proving nothing at all. This is the
    suite-green-is-not-coverage guard for its own inputs.
    """
    assert classify_screen(*ANCHOR_158) == "main_command"
    assert classify_screen(*ANCHOR_231) == "main_command"
    assert classify_screen(*CLASSIC) == "main_command"
    assert classify_screen(*DAMAGED) == "main_command"
    assert classify_screen(*MONEY) == "money_prompt"
    assert classify_screen(*PORT) == "port_trade"
    assert classify_screen(*ODD) == "unknown"

    # And the fixture that carries the prohibition really is IN canon's set,
    # rather than merely being a screen this file called money-ish.
    assert classify_screen(*MONEY) in NEVER_AUTO_ACTION_CLASSES

    assert read_current_sector(PROMPT_158).sector == 158
    assert read_current_sector(PROMPT_231).sector == 231
    assert read_current_sector(PROMPT_CLASSIC).outcome == "absent"
    assert read_current_sector(PROMPT_DAMAGED).outcome == "unreadable"
    # The two screens the gate refuses carry NO readable sector, which is
    # exactly why the gate-before-anchor ordering is load-bearing rather
    # than cosmetic: without it both would report a sector problem.
    assert read_current_sector(PROMPT_HOLDS).outcome == "absent"
    assert read_current_sector(PROMPT_ODD).outcome == "absent"


# --------------------------------------------------------------------------
# Ports
# --------------------------------------------------------------------------


class ScriptedSession:
    """A session that hands out pre-written screens, one per boundary.

    ``screens[i]`` is the screen at boundary ``i`` -- boundary 0 is what
    the player sees before step 0's send, boundary 1 is what it sees after
    it, and so on. ``confirmations[i]`` is what step ``i``'s send reports.

    Every port call is appended to ``calls``, which is what makes the
    settle-before-you-look ordering provable rather than assumed.
    """

    def __init__(self, screens, confirmations=None, settles=None, fences=None):
        self.screens = list(screens)
        self.confirmations = list(confirmations) if confirmations is not None else None
        self.settles = list(settles) if settles is not None else None
        self.fences = list(fences) if fences is not None else None
        self.calls: list[str] = []
        self.sends: list[tuple[str, object]] = []

    @property
    def _boundary(self) -> int:
        return len(self.sends)

    def _pop(self, scripted, default):
        if scripted is None:
            return default
        return scripted.pop(0) if scripted else default

    def settle(self) -> bool:
        self.calls.append("settle")
        return self._pop(self.settles, True)

    def screen(self):
        self.calls.append("screen")
        return self.screens[self._boundary]

    def is_driver_fenced(self) -> bool:
        self.calls.append("is_driver_fenced")
        return self._pop(self.fences, False)

    def send_and_confirm(self, keystrokes, wait_prompt):
        self.calls.append("send_and_confirm")
        self.sends.append((keystrokes, wait_prompt))
        return self._pop(self.confirmations, True)


class NoSendSession(ScriptedSession):
    """The zero-bytes instrument.

    Reaching the wire at all is the failure. Nothing about the returned
    reason is trusted by the tests that use this: the assertion is that
    this method was never called, and the player's own ``sends_issued``
    counter agrees.
    """

    def send_and_confirm(self, keystrokes, wait_prompt):  # pragma: no cover - must not run
        raise AssertionError(
            f"the player sent {keystrokes!r} -- a refusal that sends first and reports "
            "afterwards is not a refusal"
        )


class PortWithout:
    """A port missing exactly one method, to prove a malformed adapter
    costs zero bytes rather than one send followed by an ``AttributeError``."""

    def __init__(self, inner, missing):
        self._inner = inner
        self._missing = missing

    def __getattr__(self, name):
        if name == object.__getattribute__(self, "_missing"):
            raise AttributeError(f"this port does not provide {name}()")
        return getattr(object.__getattribute__(self, "_inner"), name)


# --------------------------------------------------------------------------
# Macros
# --------------------------------------------------------------------------


def make_loop(steps, *, name="ore-run", start_anchor=158, draft=False):
    return Loop(
        name=name,
        steps=tuple(LoopStep(*step) for step in steps),
        start_anchor=start_anchor,
        source="recorded",
        created_ts="2026-07-26T00:00:00Z",
        draft=draft,
        path=f"/nowhere/{name}.json",
    )


# A one-step macro: press "P", expect to land back on the command prompt.
ONE_STEP = [("P", None, "main_command")]
TWO_STEPS = [("P", None, "port_trade"), ("1", None, "main_command")]


# --------------------------------------------------------------------------
# 1. ZERO BYTES -- the proof that outranks every reason string
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,session_kwargs,loop_kwargs,force,expected",
    [
        # An unrecognized screen. Canon's central invariant: the app plays
        # only taught screens and STOPs on anything else.
        ("unknown screen", {"screens": [ODD]}, {}, False, HALT_UNRECOGNIZED_SCREEN),
        # A money question. DECISIONS §A.2 -- and note the screen ALSO has
        # no readable sector, so this cell doubles as the ordering pin.
        ("money prompt", {"screens": [MONEY]}, {}, False, HALT_NEVER_AUTO_ACTION),
        # The human has the keyboard.
        ("fenced", {"screens": [ANCHOR_158], "fences": [True]}, {}, False, HALT_FENCED),
        # The stream never settled, so there is nothing safe to read.
        ("never settles", {"screens": [ANCHOR_158], "settles": [False]}, {}, False, HALT_SETTLE_FAILED),
        # Wrong sector: THE incident the start-anchor guard exists for.
        ("anchor mismatch", {"screens": [ANCHOR_231]}, {}, False, HALT_START_ANCHOR_MISMATCH),
        # An anchored macro on a prompt that states no sector.
        ("current sector absent", {"screens": [CLASSIC]}, {}, False, HALT_CURRENT_SECTOR_ABSENT),
        # An anchored macro on a half-painted prompt.
        ("current sector unreadable", {"screens": [DAMAGED]}, {}, False, HALT_CURRENT_SECTOR_UNREADABLE),
        # A legacy macro with no anchor, and no force.
        ("no recorded anchor", {"screens": [ANCHOR_158]}, {"start_anchor": None}, False,
         HALT_START_ANCHOR_MISSING),
        # Force does not rescue a DETECTED disagreement.
        ("forced mismatch", {"screens": [ANCHOR_231]}, {}, True, HALT_START_ANCHOR_MISMATCH),
        ("forced absent", {"screens": [CLASSIC]}, {}, True, HALT_CURRENT_SECTOR_ABSENT),
        ("forced unreadable", {"screens": [DAMAGED]}, {}, True, HALT_CURRENT_SECTOR_UNREADABLE),
        ("forced money prompt", {"screens": [MONEY]}, {}, True, HALT_NEVER_AUTO_ACTION),
        ("forced unknown screen", {"screens": [ODD]}, {}, True, HALT_UNRECOGNIZED_SCREEN),
        # GATE-ONLY cells. Every case above is ALSO covered by the anchor
        # check, because a money question and an unrecognized screen both
        # happen to carry no readable sector -- so deleting the gate would
        # still halt them, and the two cells above would stay green for the
        # wrong reason. An unanchored macro under force waives the anchor
        # check entirely, leaving the gate as the only thing between these
        # screens and a keystroke. Measured, not assumed: with the gate
        # removed these two are the cells that fail on the RAISE.
        ("gate-only money prompt", {"screens": [MONEY]}, {"start_anchor": None}, True,
         HALT_NEVER_AUTO_ACTION),
        ("gate-only unknown screen", {"screens": [ODD]}, {"start_anchor": None}, True,
         HALT_UNRECOGNIZED_SCREEN),
        ("gate-only fence", {"screens": [ANCHOR_158], "fences": [True]}, {"start_anchor": None},
         True, HALT_FENCED),
    ],
)
def test_a_refusal_before_the_first_send_costs_zero_bytes(
    label, session_kwargs, loop_kwargs, force, expected
):
    """The headline proof, run against a port that RAISES on any send.

    If any of these cells ever sends first and reports afterwards, this
    test fails with the player's own keystroke in the message -- it cannot
    be satisfied by a player that merely returns the right reason.
    """
    session = NoSendSession(**session_kwargs)
    result = replay_loop(make_loop(ONE_STEP, **loop_kwargs), session, force=force)

    assert result.outcome == OUTCOME_HALTED, label
    assert result.reason == expected, label
    # Canon's own marker for "nothing was sent" (`macros.md`: step_i = -1).
    assert result.halted_at == -1, label
    # Three independent witnesses to the same fact: the port was never
    # asked, the player counted no attempt, and no step was traced.
    assert session.sends == [], label
    assert result.sends_issued == 0, label
    assert result.steps == (), label


def test_a_malformed_port_also_costs_zero_bytes():
    """Every port method is reached at boundary 0, so a port missing one
    fails BEFORE the first send rather than after it.

    This is why the module needs no up-front port validation: boundary 0
    runs exactly the same observe-and-gate code as every later boundary,
    so a defect that would surface at boundary 3 surfaces at boundary 0
    first -- with nothing on the wire.
    """
    for missing in ("settle", "screen", "is_driver_fenced"):
        inner = ScriptedSession(screens=[ANCHOR_158, ANCHOR_158])
        with pytest.raises(AttributeError):
            replay_loop(make_loop(ONE_STEP), PortWithout(inner, missing))
        assert inner.sends == [], missing

    # And a port with no send method at all never gets past the lookup.
    inner = ScriptedSession(screens=[ANCHOR_158, ANCHOR_158])
    with pytest.raises(AttributeError):
        replay_loop(make_loop(ONE_STEP), PortWithout(inner, "send_and_confirm"))
    assert inner.sends == []


def test_a_wrong_loop_type_is_refused_before_the_session_is_touched():
    """The archived engine took a raw dict. Accepting one here would also
    accept a look-alike whose ``steps`` is a mutable list, discarding the
    loader's frozen-tuple guarantee at the last possible moment."""
    session = NoSendSession(screens=[ANCHOR_158])
    with pytest.raises(TypeError, match="loops.loader.Loop"):
        replay_loop({"name": "ore-run", "steps": [], "start_anchor": 158}, session)
    assert session.calls == []


# --------------------------------------------------------------------------
# 2. The anchor trichotomy, held apart
# --------------------------------------------------------------------------


# (recorded anchor, boundary-0 screen) -> halt reason, or None to proceed.
_ANCHOR_GRID = [
    (158, ANCHOR_158, None),
    (158, ANCHOR_231, HALT_START_ANCHOR_MISMATCH),
    (158, CLASSIC, HALT_CURRENT_SECTOR_ABSENT),
    (158, DAMAGED, HALT_CURRENT_SECTOR_UNREADABLE),
    (None, ANCHOR_158, HALT_START_ANCHOR_MISSING),
    (None, ANCHOR_231, HALT_START_ANCHOR_MISSING),
    (None, CLASSIC, HALT_START_ANCHOR_MISSING),
    (None, DAMAGED, HALT_START_ANCHOR_MISSING),
]


@pytest.mark.parametrize("anchor,screen,expected", _ANCHOR_GRID)
def test_the_anchor_grid_unforced(anchor, screen, expected):
    session = ScriptedSession(screens=[screen, ANCHOR_158])
    result = replay_loop(make_loop(ONE_STEP, start_anchor=anchor), session, force=False)

    if expected is None:
        assert result.outcome == OUTCOME_COMPLETED
        assert session.sends == [("P", None)]
    else:
        assert result.outcome == OUTCOME_HALTED
        assert result.reason == expected
        assert session.sends == []


@pytest.mark.parametrize("anchor,screen,expected", _ANCHOR_GRID)
def test_force_changes_exactly_one_cell_of_the_grid(anchor, screen, expected):
    """Canon: force "only ever waives the nothing-to-check-against legacy
    case"; forcing past a *detected* mismatch "is the danger itself".

    Run as the same grid rather than as hand-picked cases so the claim is
    about the whole decision surface: every cell whose unforced answer is
    not :data:`FORCEABLE_HALTS` must answer identically under force.
    """
    session = ScriptedSession(screens=[screen, ANCHOR_158])
    result = replay_loop(make_loop(ONE_STEP, start_anchor=anchor), session, force=True)

    if expected in FORCEABLE_HALTS:
        # The one waivable fact: no anchor was ever recorded, so there is
        # nothing for reality to disagree with.
        assert result.outcome == OUTCOME_COMPLETED
        assert session.sends == [("P", None)]
    elif expected is None:
        assert result.outcome == OUTCOME_COMPLETED
    else:
        assert result.outcome == OUTCOME_HALTED
        assert result.reason == expected
        assert session.sends == []


def test_force_waives_exactly_one_reason_and_the_set_says_which():
    """The waiver as data, not as scattered branches. If a future edit
    makes force bypass a second halt, this set is where it has to be
    declared -- and declaring it is a canon decision, visibly."""
    assert FORCEABLE_HALTS == {HALT_START_ANCHOR_MISSING}
    assert FORCEABLE_HALTS <= HALT_REASONS


def test_an_absent_current_read_is_not_a_missing_anchor():
    """The collapse this whole section exists to prevent, stated as one
    assertion pair.

    Both screens "have no sector". One is the RECORDING having captured no
    precondition (waivable); the other is a live screen declining to say
    whether a recorded precondition holds (canon's "or can't be read at
    all" -- never waivable). A player that treated them alike would let a
    force flag replay a macro from an unknown sector.
    """
    unanchored = replay_loop(
        make_loop(ONE_STEP, start_anchor=None),
        ScriptedSession(screens=[ANCHOR_158, ANCHOR_158]),
        force=True,
    )
    unreadable_world = replay_loop(
        make_loop(ONE_STEP, start_anchor=158),
        NoSendSession(screens=[CLASSIC]),
        force=True,
    )
    assert unanchored.outcome == OUTCOME_COMPLETED
    assert unreadable_world.outcome == OUTCOME_HALTED
    assert unreadable_world.reason == HALT_CURRENT_SECTOR_ABSENT
    assert unreadable_world.reason not in FORCEABLE_HALTS


def test_absent_and_unreadable_halt_alike_but_never_render_alike():
    """Same decision, different repair -- X1's whole thesis, carried into
    the player's answer instead of flattened out of it."""
    absent = replay_loop(make_loop(ONE_STEP), NoSendSession(screens=[CLASSIC]))
    unreadable = replay_loop(make_loop(ONE_STEP), NoSendSession(screens=[DAMAGED]))

    assert absent.reason != unreadable.reason
    assert absent.anchor_read.outcome == "absent"
    assert unreadable.anchor_read.outcome == "unreadable"
    assert unreadable.anchor_read.reason == "damaged_command_prompt"


def test_the_anchor_is_rechecked_by_every_invocation():
    """Canon scopes the check to "before the first send of EVERY replay
    invocation", which is what gives a repeating run its per-cycle
    re-check for free. The ship moves between invocations here."""
    loop = make_loop(ONE_STEP)
    first = replay_loop(loop, ScriptedSession(screens=[ANCHOR_158, ANCHOR_158]))
    assert first.outcome == OUTCOME_COMPLETED

    moved = NoSendSession(screens=[ANCHOR_231])
    second = replay_loop(loop, moved)
    assert second.reason == HALT_START_ANCHOR_MISMATCH
    assert moved.sends == []


# --------------------------------------------------------------------------
# 3. never-auto-action -- refused before EVERY send
# --------------------------------------------------------------------------


def test_a_money_prompt_mid_loop_is_refused_before_that_step_sends():
    """The mid-loop half of §A.2, and the one a "check it at entry" player
    would fail.

    Boundary 0 is a clean command prompt so the run legitimately starts;
    step 0's send lands on a money question; step 1's send must never
    happen. The port raises on the SECOND send, so a player that pressed
    on would fail loudly rather than merely report the wrong reason.
    """

    class RaiseOnSecondSend(ScriptedSession):
        def send_and_confirm(self, keystrokes, wait_prompt):
            if self.sends:
                raise AssertionError(
                    f"the player sent {keystrokes!r} into a money prompt mid-loop"
                )
            return super().send_and_confirm(keystrokes, wait_prompt)

    session = RaiseOnSecondSend(screens=[ANCHOR_158, MONEY, ANCHOR_158])
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.outcome == OUTCOME_HALTED
    assert result.reason == HALT_NEVER_AUTO_ACTION
    assert result.halted_at == 0
    assert result.sends_issued == 1
    assert session.sends == [("P", None)]
    # The trace carries the step that WAS sent, including what it landed on.
    assert result.steps[-1].observed_class == "money_prompt"


def test_a_macro_recorded_to_answer_a_money_prompt_still_halts_there():
    """The exemption §A.2 grants is for a *human-armed, guarded* rule. A
    stored macro has neither field, so a recording that expected the money
    screen does not get to fire on it -- the prohibition is checked before
    the class comparison precisely so a match cannot license a send.

    This is the fail-closed direction, and it is not free: a real taught
    trade macro answering "How many holds..." halts here. That is the
    intended behaviour until the arming substrate exists.
    """
    taught_to_answer_money = [("P", None, "money_prompt"), ("50", None, "main_command")]
    # Boundary 0 is clean, so step 0 legitimately sends; the money screen it
    # lands on is what step 1 would have been pressed into.
    scripted = ScriptedSession(screens=[ANCHOR_158, MONEY, ANCHOR_158])
    result = replay_loop(make_loop(taught_to_answer_money), scripted)

    assert result.reason == HALT_NEVER_AUTO_ACTION
    assert result.reason != HALT_POST_CLASS  # not "the class disagreed" -- forbidden
    assert scripted.sends == [("P", None)]


def test_the_refusal_is_derived_from_canons_set_not_restated():
    """``classify.py``: the pin "only holds while consumers derive their
    refusals from this name rather than restating it... anything that
    later decides whether a rule may fire owes the same."

    Grep would not prove this -- a module can name the symbol and still
    branch on a literal. So the set is monkeypatched and the player's
    behaviour has to follow it.
    """
    # The same object, not a same-looking copy -- the identity pin the
    # loader already uses for `store._read_document`.
    assert player_mod.NEVER_AUTO_ACTION_CLASSES is NEVER_AUTO_ACTION_CLASSES
    # And no literal restatement of a member of the set anywhere in it.
    for member in NEVER_AUTO_ACTION_CLASSES:
        assert f'"{member}"' not in PLAYER_SRC and f"'{member}'" not in PLAYER_SRC

    # A class canon has not forbidden fires normally...
    ok = ScriptedSession(screens=[ANCHOR_158, PORT, ANCHOR_158])
    assert replay_loop(make_loop(TWO_STEPS), ok).outcome == OUTCOME_COMPLETED


def test_widening_canons_set_widens_the_players_refusal(monkeypatch):
    """The other half of the derivation claim: add a class to canon's set
    and the player refuses it the same day, with no second edit."""
    monkeypatch.setattr(
        player_mod, "NEVER_AUTO_ACTION_CLASSES", NEVER_AUTO_ACTION_CLASSES | {"port_trade"}
    )
    session = NoSendSession(screens=[PORT])
    result = replay_loop(make_loop(TWO_STEPS, start_anchor=None), session, force=True)

    assert result.reason == HALT_NEVER_AUTO_ACTION
    assert session.sends == []


# --------------------------------------------------------------------------
# 4. Stop-on-unknown, at every boundary
# --------------------------------------------------------------------------


def test_an_unknown_screen_mid_loop_halts_before_the_next_send():
    class RaiseOnSecondSend(ScriptedSession):
        def send_and_confirm(self, keystrokes, wait_prompt):
            if self.sends:
                raise AssertionError(f"the player sent {keystrokes!r} into an unknown screen")
            return super().send_and_confirm(keystrokes, wait_prompt)

    session = RaiseOnSecondSend(screens=[ANCHOR_158, ODD, ANCHOR_158])
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.reason == HALT_UNRECOGNIZED_SCREEN
    assert result.halted_at == 0
    assert session.sends == [("P", None)]


def test_an_expected_post_class_of_unknown_does_not_match_itself():
    """Canon: "An ``unknown`` classification, OR any mismatch against what
    was recorded, is a divergence" -- the two are independent, so a macro
    that recorded ``unknown`` (3 steps of the real archived corpus do) must
    halt on the novelty rather than "match" a screen nobody can name.

    A player that compared first and gated afterwards would report
    ``completed`` here, having pressed on into an unrecognized screen.
    """
    taught_unknown = [("P", None, "unknown")]
    session = ScriptedSession(screens=[ANCHOR_158, ODD])
    result = replay_loop(make_loop(taught_unknown), session)

    assert result.outcome == OUTCOME_HALTED
    assert result.reason == HALT_UNRECOGNIZED_SCREEN
    assert result.steps[-1].expected_post_class == "unknown"
    assert result.steps[-1].observed_class == "unknown"


def test_the_gate_outranks_the_anchor_check_in_what_it_reports():
    """Both halt, so this is a reporting choice, not a safety one -- pinned
    because it is a choice.

    A ``money_prompt`` and an ``unknown`` screen both carry no sector
    bracket, so an anchor-first player would diagnose "current sector
    absent" on a screen whose real problem is that the server is blocked
    on a money question.
    """
    money = replay_loop(make_loop(ONE_STEP), NoSendSession(screens=[MONEY]))
    odd = replay_loop(make_loop(ONE_STEP), NoSendSession(screens=[ODD]))

    assert money.reason == HALT_NEVER_AUTO_ACTION
    assert odd.reason == HALT_UNRECOGNIZED_SCREEN
    assert HALT_CURRENT_SECTOR_ABSENT not in {money.reason, odd.reason}


def test_a_fence_mid_loop_stops_within_one_send_step():
    session = ScriptedSession(
        screens=[ANCHOR_158, PORT, ANCHOR_158], fences=[False, True]
    )
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.reason == HALT_FENCED
    assert session.sends == [("P", None)]


# --------------------------------------------------------------------------
# 5. Settle before you look
# --------------------------------------------------------------------------


def test_every_read_is_preceded_by_a_settle():
    """X1: ``state`` is the cheap poll and does not settle, so the caller
    must settle first and poll after. This module is that caller, and the
    ordering is proven from the port's own call log rather than asserted.

    A mid-paint read yields ``unreadable`` at best and a plausible-wrong
    sector at worst -- the latter satisfies the anchor check and replays
    from the wrong sector, which is the incident canon exists to prevent.
    """
    session = ScriptedSession(screens=[ANCHOR_158, PORT, ANCHOR_158])
    replay_loop(make_loop(TWO_STEPS), session)

    assert "screen" in session.calls
    for index, call in enumerate(session.calls):
        if call == "screen":
            assert session.calls[index - 1] == "settle", session.calls

    # And the shape of a whole run: settle/read/gate at each boundary, one
    # send between consecutive boundaries, never a send before a boundary.
    boundary = ["settle", "screen", "is_driver_fenced"]
    assert session.calls == boundary + ["send_and_confirm"] + boundary + [
        "send_and_confirm"
    ] + boundary


def test_a_session_that_never_settles_is_never_read_or_sent_to():
    session = NoSendSession(screens=[ANCHOR_158], settles=[False])
    result = replay_loop(make_loop(ONE_STEP), session)

    assert result.reason == HALT_SETTLE_FAILED
    assert session.calls == ["settle"]
    assert result.anchor_read is None


def test_a_settle_failure_mid_loop_halts_without_reading():
    session = ScriptedSession(
        screens=[ANCHOR_158, PORT, ANCHOR_158], settles=[True, False]
    )
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.reason == HALT_SETTLE_FAILED
    assert result.halted_at == 0
    assert session.sends == [("P", None)]
    assert result.steps[-1].observed_class is None


@pytest.mark.parametrize("bad", [None, "just a string", b"bytes", ("only-one",), (1, 2)])
def test_a_port_that_cannot_hand_back_a_screen_halts_rather_than_crashing(bad):
    """An adapter fault becomes a traced, typed refusal instead of an
    untraced exception from inside the guard layer -- and stays a DIFFERENT
    code from every game surprise, because "could not read" and "read, and
    it says nothing" want different repairs."""

    class OddScreen(NoSendSession):
        def screen(self):
            self.calls.append("screen")
            return bad

    result = replay_loop(make_loop(ONE_STEP), OddScreen(screens=[ANCHOR_158]))
    assert result.reason == HALT_SCREEN_UNREADABLE
    assert result.anchor_read is None


# --------------------------------------------------------------------------
# 6. Per-step confirm and post-class
# --------------------------------------------------------------------------


def test_an_unconfirmed_send_halts_without_classifying_the_screen():
    """Canon: replay "does not then try to classify a screen it already
    knows is untrustworthy". Proven from the call log: there is no
    observation after the failed send at all."""
    session = ScriptedSession(screens=[ANCHOR_158, ODD, ANCHOR_158], confirmations=[False])
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.reason == HALT_CONFIRM_FAILED
    assert result.halted_at == 0
    assert result.steps[-1].confirmed is False
    assert result.steps[-1].observed_class is None
    # One boundary, one send, and then nothing -- no second settle/read.
    assert session.calls == ["settle", "screen", "is_driver_fenced", "send_and_confirm"]


@pytest.mark.parametrize(
    "returned", [("prompt", 0.4, True), ("prompt", 0.4, False), 1, "yes", [True]]
)
def test_a_port_that_forwards_the_settle_layers_tuple_is_not_read_as_confirmed(returned):
    """The adapter mistake this port's own naming invites.

    ``settle.send_and_confirm`` returns ``(reason, elapsed, confirmed)``
    and the port method has the same name, so "just forward it" is the
    obvious implementation -- and every one of those tuples is TRUTHY. A
    truthiness test would read every send as confirmed and pump the whole
    macro through, which is the precise failure canon's send-and-confirm
    invariant exists to make impossible. Fails closed instead.
    """

    class Forwarding(ScriptedSession):
        def send_and_confirm(self, keystrokes, wait_prompt):
            self.sends.append((keystrokes, wait_prompt))
            return returned

    session = Forwarding(screens=[ANCHOR_158, ANCHOR_158, ANCHOR_158])
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.reason == HALT_CONFIRM_FAILED
    assert result.halted_at == 0
    # One send attempted, and step 1 never reached.
    assert len(session.sends) == 1


@pytest.mark.parametrize("returned", [("timeout", 8.0), ("idle", 0.3), 1, "settled"])
def test_a_port_that_forwards_wait_until_settleds_tuple_is_not_read_as_settled(returned):
    """The same trap one layer up: ``wait_until_settled`` returns
    ``(reason, elapsed)`` and ``("timeout", 8.0)`` is truthy, so a
    truthiness test would read a settle that TIMED OUT as one that
    succeeded -- and then read the screen anyway."""

    class Forwarding(NoSendSession):
        def settle(self):
            self.calls.append("settle")
            return returned

    session = Forwarding(screens=[ANCHOR_158])
    result = replay_loop(make_loop(ONE_STEP), session)

    assert result.reason == HALT_SETTLE_FAILED
    assert session.calls == ["settle"]


def test_a_class_mismatch_halts_with_the_trace_through_the_failing_step():
    session = ScriptedSession(screens=[ANCHOR_158, ANCHOR_158, ANCHOR_158])
    result = replay_loop(make_loop(TWO_STEPS), session)  # step 0 expects port_trade

    assert result.reason == HALT_POST_CLASS
    assert result.halted_at == 0
    assert len(result.steps) == 1
    assert result.steps[0].expected_post_class == "port_trade"
    assert result.steps[0].observed_class == "main_command"
    assert session.sends == [("P", None)]


def test_the_recorded_wait_prompt_is_passed_through_untouched():
    """Case-sensitivity is a hard rule and the loader already proved the
    pattern compiles under exactly the call the settle layer makes. The
    player's job is to not "helpfully" alter it on the way past."""
    steps = [("50", "Your offer", "main_command")]
    session = ScriptedSession(screens=[ANCHOR_158, ANCHOR_158])
    replay_loop(make_loop(steps), session)

    assert session.sends == [("50", "Your offer")]


def test_a_bare_enter_step_is_sent_as_the_empty_string():
    """61 of the real corpus's 245 steps are ``""`` (canon's bare
    Enter/accept-default). A truthiness check anywhere on the send path
    would silently drop a quarter of every taught macro."""
    steps = [("", None, "main_command")]
    session = ScriptedSession(screens=[ANCHOR_158, ANCHOR_158])
    result = replay_loop(make_loop(steps), session)

    assert result.outcome == OUTCOME_COMPLETED
    assert session.sends == [("", None)]


def test_a_completed_run_traces_every_step_in_order():
    session = ScriptedSession(screens=[ANCHOR_158, PORT, ANCHOR_158])
    result = replay_loop(make_loop(TWO_STEPS), session)

    assert result.outcome == OUTCOME_COMPLETED
    assert result.reason is None and result.halted_at is None
    assert result.sends_issued == 2
    assert [step.index for step in result.steps] == [0, 1]
    assert [step.input for step in result.steps] == ["P", "1"]
    assert [step.observed_class for step in result.steps] == ["port_trade", "main_command"]
    assert all(step.confirmed for step in result.steps)
    assert result.anchor_read.sector == 158


# --------------------------------------------------------------------------
# 7. The result type
# --------------------------------------------------------------------------


def test_the_result_cannot_claim_completion_while_carrying_a_halt():
    with pytest.raises(ValueError, match="reason accompanies exactly"):
        ReplayResult(OUTCOME_COMPLETED, "x", (), 0, reason=HALT_CONFIRM_FAILED)
    with pytest.raises(ValueError, match="reason accompanies exactly"):
        ReplayResult(OUTCOME_HALTED, "x", (), 0, halted_at=0)
    with pytest.raises(ValueError, match="halted_at index accompanies exactly"):
        ReplayResult(OUTCOME_HALTED, "x", (), 0, reason=HALT_CONFIRM_FAILED)
    with pytest.raises(ValueError, match="is not one of"):
        ReplayResult(OUTCOME_HALTED, "x", (), 0, reason="made_up", halted_at=0)
    with pytest.raises(ValueError, match="outcome"):
        ReplayResult("fine", "x", (), 0)


def test_the_result_has_no_truthiness_shortcut():
    """``SectorRead``'s omission, for the same reason: there must be no
    expression that folds ``halted`` into a passing value at a call site.

    ``bool()`` of a plain object is True, so ``if replay_loop(...):`` reads
    as success on a halt -- which is exactly why neither type defines
    ``__bool__``/``ok`` to make that idiom look sanctioned. The assertion
    is that no such member exists to reach for.
    """
    for attribute in ("__bool__", "ok", "success", "halted"):
        assert not hasattr(ReplayResult, attribute), attribute
    assert not hasattr(StepTrace, "__bool__")


def test_a_result_carries_no_screen_text():
    """DECISIONS §C.2 / §C.2.1: a structured answer must not carry
    server-echoed content. Every string in a result is either a closed
    vocabulary member or came off the macro on disk."""
    session = ScriptedSession(screens=[ANCHOR_158, ODD, ANCHOR_158])
    result = replay_loop(make_loop(TWO_STEPS), session)

    rendered = repr(result)
    assert "Ferrengi" not in rendered
    assert "Command [TL=" not in rendered
    assert "Sector  :" not in rendered


# --------------------------------------------------------------------------
# 8. The loader seam
# --------------------------------------------------------------------------


def test_a_macro_loaded_from_disk_replays(tmp_path):
    """End to end across the two slices this one consumes: a real document
    on disk, through X2's loader, into the player, against X1's read."""
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    (skills / "ore-run.json").write_text(
        json.dumps(
            {
                "name": "ore-run",
                "source": "recorded",
                "start_anchor": 158,
                "steps": [
                    {"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"},
                    {"input": "1", "wait_prompt": None, "expected_post_class": "main_command"},
                ],
            }
        ),
        encoding="utf-8",
    )

    loop = load_loop("ore-run", state_dir=tmp_path)
    session = ScriptedSession(screens=[ANCHOR_158, PORT, ANCHOR_158])
    result = replay_loop(loop, session)

    assert result.outcome == OUTCOME_COMPLETED
    assert result.loop_name == "ore-run"
    assert session.sends == [("P", None), ("1", None)]

    # ... and the same macro replayed from the wrong sector does not.
    moved = NoSendSession(screens=[ANCHOR_231])
    assert replay_loop(loop, moved).reason == HALT_START_ANCHOR_MISMATCH


# --------------------------------------------------------------------------
# 9. Structural pins -- the bounds this slice was built inside
# --------------------------------------------------------------------------


def test_the_player_reaches_the_wire_through_exactly_one_call():
    """The pin that replaced ``loops/``'s blanket "cannot send" claim.

    ``send_and_confirm`` is IN the shared blocklist, so this is not a
    weakened scan: the scanner still reports the player's send, and this
    asserts there is exactly ONE of them. A second send path -- of any
    shape the scanner knows, including a reflected ``getattr`` -- turns
    this list into two entries and fails.
    """
    violations = _send_violations(PLAYER_SRC, allow_session_modules=ALLOWED_SESSION_MODULES)
    assert violations == [".send_and_confirm"]
    assert "send_and_confirm" in _SEND_SYMBOLS


def test_the_two_waived_session_modules_are_themselves_provably_pure():
    """The waiver is not taken on trust. ``classify`` and ``state_parser``
    are the only ``session/`` modules the player may import, and they earn
    that by passing the same no-send scan -- transitively, since neither
    imports anything from this package at all, so their import closure is
    the standard library.
    """
    for name in sorted(ALLOWED_SESSION_MODULES):
        source = (PKG_ROOT / "session" / f"{name}.py").read_text(encoding="utf-8")
        assert _send_violations(source) == [], name

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # `from __future__ import annotations` is the one relative-
                # level-0 stdlib import these carry; anything reaching into
                # the package would break the transitive claim.
                assert not node.level, f"{name}: relative import {node.module!r}"
                assert not (node.module or "").startswith("tw2002_aiclient"), name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("tw2002_aiclient"), name


def test_the_player_cannot_acquire_a_session():
    """No default, no factory, no module-level session. The caller supplies
    the way to press keys or there is no replay -- which is what keeps
    ``loops/`` unable to reach the game on its own."""
    parameters = inspect.signature(replay_loop).parameters
    assert parameters["session"].default is inspect.Parameter.empty
    assert list(parameters) == ["loop", "session", "force"]
    assert parameters["force"].kind is inspect.Parameter.KEYWORD_ONLY


def test_no_run_loop_snuck_in():
    """The slice boundary, enforced. Repetition belongs to the run-loop
    that owns the rails making it safe (turn-budget, stop-loss, hazard,
    arm-confirm); shipping ``cycles=N`` here would ship the repetition
    without any of them.

    Checked structurally rather than by text search -- the module's own
    docstring says the word "cycles" while explaining its absence, and a
    grep that green-lit on prose would be measuring the comment.
    """
    tree = ast.parse(PLAYER_SRC)

    # Exactly ONE loop statement in the whole module, and it walks the
    # macro's own steps. Wrapping it in a repetition means a second one.
    loops = [node for node in ast.walk(tree) if isinstance(node, (ast.For, ast.While))]
    assert len(loops) == 1
    only = loops[0]
    assert isinstance(only, ast.For)
    assert isinstance(only.iter, ast.Call) and only.iter.func.id == "enumerate"
    assert ast.unparse(only.iter.args[0]) == "loop.steps"

    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    # No writer, no recorder, no daemon driver, no CLI verb.
    for banned in ("play", "play_loop", "record", "write", "autoloop", "run"):
        assert banned not in functions, banned

    writes = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"write_text", "write_bytes", "mkdir", "unlink", "rename", "dump"}
    ]
    assert writes == []


def test_no_bypass_flag_exists_for_the_never_auto_refusal():
    """§A.2's exemption is for a human-armed guarded rule, and the arm gate
    is canonically "a required, external input... not an internal
    self-check the loop could grant itself". A flag here would BE the
    self-granted arming.
    """
    parameters = set(inspect.signature(replay_loop).parameters)
    for banned in ("allow_money", "allow_never_auto", "unsafe", "armed", "unattended"):
        assert banned not in parameters, banned


def test_the_reason_vocabulary_is_closed_and_fully_reachable():
    """A reason nothing can report forbids nothing; a reason not in the set
    would crash the result type. Both directions pinned."""
    reported = {
        HALT_SETTLE_FAILED,
        HALT_SCREEN_UNREADABLE,
        HALT_FENCED,
        HALT_NEVER_AUTO_ACTION,
        HALT_UNRECOGNIZED_SCREEN,
        HALT_START_ANCHOR_MISSING,
        HALT_START_ANCHOR_MISMATCH,
        HALT_CURRENT_SECTOR_ABSENT,
        HALT_CURRENT_SECTOR_UNREADABLE,
        HALT_CONFIRM_FAILED,
        HALT_POST_CLASS,
    }
    assert reported == HALT_REASONS
    # Canon's and the archive's own spellings, carried rather than re-coined.
    assert HALT_START_ANCHOR_MISMATCH == "start_anchor_mismatch"
    assert HALT_CONFIRM_FAILED == "confirm_failed"
    assert HALT_POST_CLASS == "post_class"
    # The one code canon's catalog already renders a label for.
    from tw2002_aiclient.cockpit.stopbanner import INTERVENTION_REASON_LABELS

    assert HALT_FENCED in INTERVENTION_REASON_LABELS
