"""The stop-loss floor (WO-P2-G4-X5) -- credits observation and the rail
that halts on it.

This slice exists because of one specific cheat, and the WO names it: a
``--floor`` that parses, stores, and is never checked is a few lines, reads
as a feature, and demos perfectly. Everything below serves one of four
claims, and the fourth is the one that makes the other three worth having.

1. **The balance is STRICT.** A port's own price quote is not a balance.
   AP-13 records that using the loose extraction "means the stop-loss can be
   defeated by a price quote on the wrong screen -- exactly what happened
   live before this was fixed", so the price-quote fixtures below are real
   captured sentences and the pin is enforced against the compiled patterns,
   not the source text.

2. **Fail-closed is the whole point.** ``credits_unknown`` HALTs. So does
   ``credits_stale``, and so does a port that answers with a tuple. There is
   no input to :func:`_check_floor` that means "could not establish the
   balance, proceed anyway", and the ladder is exercised branch by branch to
   prove it.

3. **The check happens before the send, at every boundary.** Proven against
   raising ports, so a refusal that sent first and reported afterwards fails
   the assertion rather than passing it. A once-at-launch floor is tested
   for explicitly and is not what this ships.

4. **The cheat itself is injected, and the guard tests go red.** Three
   mutations -- neuter the decision, cut its call sites, or make an unknown
   balance proceed -- are applied to the real module source and run through
   the *same* scenario a passing test above asserts on. If any of them still
   passed, the pin above it would be ceremony.

Vacuity is the standing hazard here (X3 found 13 of 16 grid cells passing
because a different guard fired), so every floor scenario runs on a screen
that is otherwise CLEAN -- anchor matching, classification recognized, not
fenced, not aborted -- and every halt assertion is paired with a positive
control that completes on the same fixtures with a healthier balance.
"""

from __future__ import annotations

import ast
import itertools
import math
import re
import sys
import threading
import types
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import stopbanner
from tw2002_aiclient.loops import player as player_mod
from tw2002_aiclient.loops.player import (
    CREDITS_STALE_MS,
    HALT_ABORTED,
    HALT_CREDITS_STALE,
    HALT_CREDITS_UNKNOWN,
    HALT_CREDITS_UNREADABLE,
    HALT_FENCED,
    HALT_FLOOR_REACHED,
    HALT_NEVER_AUTO_ACTION,
    HALT_REASONS,
    OUTCOME_COMPLETED,
    OUTCOME_HALTED,
    _check_floor,
    replay_loop,
)
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session import session as session_mod
from tw2002_aiclient.session import state_parser as sp
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.state_parser import (
    CreditsRead,
    CreditsSnapshot,
    read_credits_balance,
)

# X3's and X4's fixtures and harnesses, imported rather than re-typed -- a
# second copy of a `money_prompt` is how two suites start disagreeing about
# what one looks like. `test_loop_player.py` re-derives every classification
# from the live code, so these arrive already proven.
from .test_autoloop import (
    ONE_STEP,
    TWO_STEPS,
    Server,
    WireSession,
    make_runner,
    run_to_completion,
    write_macro,
)
from .test_loop_player import (
    ANCHOR_158,
    MONEY,
    NoSendSession,
    ScriptedSession,
    make_loop,
)

PLAYER_PATH = Path(player_mod.__file__).resolve()
PLAYER_SRC = PLAYER_PATH.read_text(encoding="utf-8")
SESSION_PATH = Path(session_mod.__file__).resolve()

STALE_S = CREDITS_STALE_MS / 1000.0


# ==========================================================================
# Fixtures -- real captured shapes
# ==========================================================================
#
# The price quotes are the archive's own live captures, quoted in
# `state_parser.credits_balance`'s docstring and in AP-13. They are the
# defeat this module exists to refuse, so they are used verbatim.

QUOTE_SELL = "We'll sell them for 132 credits."
QUOTE_BUY = "We'll buy them for 2,214 credits."
QUOTE_FINAL = "Our final offer is 4,187 credits."
PRICE_QUOTES = (QUOTE_SELL, QUOTE_BUY, QUOTE_FINAL)

# The real captured two-readings-on-one-screen case (`state_parser`'s own
# docstring: "...You have 100,101 credits...<accept the offer>...You have
# 100,485 credits..." on ONE rendered screen).
BALANCE_BEFORE = "You have 100,101 credits."
BALANCE_AFTER = "You have 100,485 credits."
SHIP_INFO_LINE = "Credits    : 100,485"

# A haggle screen is MADE of price quotes -- this is where a loose
# extraction reliably reports the wrong number, not merely occasionally.
HAGGLE_SCREEN = (
    "Docking...\n"
    "Commerce report for Aegis: 1 Fuel Ore\n"
    f"{QUOTE_BUY}\n"
    "Your offer [2450] ? \n"
    f"{QUOTE_FINAL}\n"
)


def _screen_with(body: str) -> str:
    """A real settled `main_command` screen carrying `body` above the
    prompt -- so a balance read here is read off the same shape a live run
    actually sees, not off a bare line."""
    return f"{body}\n{ANCHOR_158[0]}"


# ==========================================================================
# 1 -- the strict balance parser
# ==========================================================================


@pytest.mark.parametrize("quote", PRICE_QUOTES)
def test_a_port_price_quote_is_never_a_balance(quote):
    """AP-13's defeat, refused. These are live-captured sentences, and the
    loose `(\\d[\\d,]*)\\s+credits` extraction the archive shipped matches
    every one of them."""
    assert read_credits_balance(quote).outcome == sp.OUTCOME_ABSENT


def test_a_whole_haggle_screen_states_no_balance():
    """The screen where money is actually being spent. A stop-loss that
    read a balance here would read the ASK, and would read it as cash."""
    verdict = read_credits_balance(HAGGLE_SCREEN)
    assert verdict.outcome == sp.OUTCOME_ABSENT
    assert verdict.balance is None


def test_the_compiled_patterns_themselves_refuse_a_price_quote():
    """The structural half, enforced against every ``re.Pattern`` the module
    defines rather than against its source text.

    A source scan would trip over the module's own docstring, which has to
    name the loose shape in order to explain why it is absent -- the
    docstrings-are-nodes trap. Walking the compiled objects cannot be fooled
    that way, and it also catches a pattern added later that nobody thought
    to test behaviourally.
    """
    patterns = [
        (name, value)
        for name, value in vars(sp).items()
        if isinstance(value, re.Pattern)
    ]
    assert patterns, "no compiled patterns found -- this pin is measuring nothing"
    for name, pattern in patterns:
        for quote in PRICE_QUOTES:
            assert not pattern.search(quote), f"{name} matched a price quote: {quote!r}"


def test_the_last_balance_on_the_grid_wins():
    """Canon's Last-Match Invariant on the field where it decides money:
    the pre-trade reading is still on the grid when the post-trade one
    prints, and pyte has no scrollback to push it off."""
    screen = f"{BALANCE_BEFORE}\n<accept the offer>\n{BALANCE_AFTER}\n"
    verdict = read_credits_balance(screen)
    assert verdict.outcome == sp.OUTCOME_READ
    assert verdict.balance == 100485


def test_position_decides_the_last_match_not_pattern_priority():
    """The archive tried "You have N credits" FIRST and only fell back to
    the label form -- a PRIORITY order wearing a last-match's clothes. A
    stale `You have` line above a fresher `Credits :` line below it would
    win, which on this field means the floor decides on the balance from
    before the spend.
    """
    screen = f"You have 100,101 credits.\nCredits    : 42\n"
    verdict = read_credits_balance(screen)
    assert verdict.balance == 42
    assert verdict.source == sp.SOURCE_CREDITS_LABEL

    # ...and the other way round, so this is a position rule and not a
    # second priority order pointing the other way.
    verdict = read_credits_balance("Credits    : 42\nYou have 100,101 credits.\n")
    assert verdict.balance == 100101
    assert verdict.source == sp.SOURCE_YOU_HAVE_CREDITS


def test_a_damaged_label_is_unreadable_not_absent():
    """A render taken mid-paint: the claim was opened and the number is not
    there yet. "I could not finish reading it" is not "there is nothing to
    read", and the whole trichotomy exists so those never collapse."""
    verdict = read_credits_balance("Credits    :\n")
    assert verdict.outcome == sp.OUTCOME_UNREADABLE
    assert verdict.reason == sp.REASON_DAMAGED_CREDITS_LABEL
    assert verdict.balance is None


def test_a_damaged_claim_after_a_good_one_still_reads_unreadable():
    """Last-match applied to the DAMAGE check too. A resolved balance
    earlier on the grid does not rehabilitate a damaged claim printed after
    it -- reading the earlier number would be first-match-wins by the back
    door, and on this field the earlier number predates the spend."""
    verdict = read_credits_balance(f"{BALANCE_AFTER}\nCredits    :\n")
    assert verdict.outcome == sp.OUTCOME_UNREADABLE


def test_a_half_painted_you_have_reads_absent_and_that_narrowing_is_disclosed():
    """The disclosed limit, pinned so it stays a decision rather than
    becoming a surprise: `You have 100,4` has no prefix that unambiguously
    promises a balance (`You have 3 fighters` opens identically), so it is
    reported ABSENT, not unreadable.

    Nothing is lost safety-wise, and the next test proves it: both non-read
    outcomes leave the sticky balance untouched, so the reading ages and the
    staleness gate is what catches it.
    """
    assert read_credits_balance("You have 100,4").outcome == sp.OUTCOME_ABSENT
    assert read_credits_balance("You have 3 fighters aboard.").outcome == sp.OUTCOME_ABSENT


@pytest.mark.parametrize("value", [None, b"You have 5 credits", 500, {"credits": 5}, 5.0])
def test_a_non_screen_is_unreadable_never_absent(value):
    """"Handed something that is not a screen" is a failure to LOOK, and it
    must not render as a definite negative about the balance."""
    verdict = read_credits_balance(value)
    assert verdict.outcome == sp.OUTCOME_UNREADABLE
    assert verdict.reason == sp.REASON_NOT_TEXT


def test_the_read_verdict_pairs_its_fields():
    """The invariant is the class, not a convention: a number cannot exist
    beside a verdict that did not establish one."""
    with pytest.raises(ValueError):
        CreditsRead(outcome=sp.OUTCOME_ABSENT, balance=500)
    with pytest.raises(ValueError):
        CreditsRead(outcome=sp.OUTCOME_READ, balance=500)  # no source
    with pytest.raises(ValueError):
        CreditsRead(outcome=sp.OUTCOME_READ)  # no balance
    with pytest.raises(ValueError):
        CreditsRead(outcome="fine", balance=None)
    # `isinstance(True, int)` -- an unguarded check arms a balance of 1.
    with pytest.raises(ValueError):
        CreditsRead(
            outcome=sp.OUTCOME_READ, balance=True, source=sp.SOURCE_YOU_HAVE_CREDITS
        )


def test_neither_credits_type_has_a_truthiness_shortcut():
    """No ``__bool__``, no ``ok``. A caller must pass through the outcome to
    learn anything, so there is no expression that folds "we could not read
    the balance" into "the balance is fine" -- which on a stop-loss IS the
    defeat."""
    for cls in (CreditsRead, CreditsSnapshot):
        assert "__bool__" not in vars(cls)
        assert not hasattr(cls, "ok")
    # And the failure the omission prevents, made concrete: every verdict is
    # truthy, so `if verdict:` cannot be a freshness test even by accident.
    assert bool(sp.credits_never_observed()) is True
    assert bool(CreditsRead(outcome=sp.OUTCOME_ABSENT)) is True


# ==========================================================================
# 2 -- the sticky store on Session
# ==========================================================================


def _session(tmp_path) -> Session:
    return Session("fake-host", 0, None, str(tmp_path))


def test_the_balance_is_absent_until_something_states_one(tmp_path):
    snapshot = _session(tmp_path).credits_snapshot()
    assert snapshot.outcome == sp.OUTCOME_ABSENT
    assert snapshot.balance is None
    assert snapshot.age_s is None


def test_a_balance_is_captured_with_a_real_age(tmp_path):
    session = _session(tmp_path)
    session.observe_credits(_screen_with(BALANCE_AFTER))
    snapshot = session.credits_snapshot()
    assert snapshot.outcome == sp.OUTCOME_READ
    assert snapshot.balance == 100485
    assert 0 <= snapshot.age_s < 1.0


def test_a_price_quote_never_becomes_the_sticky_balance(tmp_path):
    """End to end through the capture point, not only through the parser --
    this is the path a live haggle actually takes."""
    session = _session(tmp_path)
    session.observe_credits(HAGGLE_SCREEN)
    assert session.credits_snapshot().outcome == sp.OUTCOME_ABSENT
    assert session.last_credits is None


@pytest.mark.parametrize(
    "screen",
    [
        pytest.param(ANCHOR_158[0], id="no-claim-at-all"),
        pytest.param("Credits    :", id="damaged-claim"),
        pytest.param(HAGGLE_SCREEN, id="price-quotes-only"),
    ],
)
def test_a_screen_that_states_no_balance_never_clobbers_the_last_one(tmp_path, screen):
    """The non-clobber contract. A reading that vanished would look to the
    floor exactly like one that was never taken, and the two want different
    repairs -- so an intervening command prompt lets the balance AGE rather
    than erasing it, and staleness is what acts on the age."""
    session = _session(tmp_path)
    session.observe_credits(_screen_with(BALANCE_AFTER))
    session.observe_credits(screen)
    assert session.credits_snapshot().balance == 100485


def test_a_damaged_claim_never_writes_a_balance(tmp_path):
    """The safety-relevant half of the trichotomy: `unreadable` is not a
    reading, so it must not reach the sticky pair even as a first write."""
    session = _session(tmp_path)
    session.observe_credits("Credits    :")
    assert session.credits_snapshot().outcome == sp.OUTCOME_ABSENT


def test_the_snapshot_rejects_an_age_that_would_read_as_fresh():
    """NaN is the danger, not a type error: ``nan > limit`` is False, so an
    un-guarded staleness ladder reads a NaN age as PERFECTLY FRESH and arms
    an unbounded floor. Negative is the same failure with a sign."""
    ok = CreditsSnapshot(outcome=sp.OUTCOME_READ, balance=500, age_s=0.5)
    assert ok.age_s == 0.5
    for bad in (float("nan"), float("inf"), -0.1, True):
        with pytest.raises(ValueError):
            CreditsSnapshot(outcome=sp.OUTCOME_READ, balance=500, age_s=bad)
    with pytest.raises(ValueError):
        CreditsSnapshot(outcome=sp.OUTCOME_READ, balance=500)  # no age
    with pytest.raises(ValueError):
        CreditsSnapshot(outcome=sp.OUTCOME_ABSENT, balance=500, age_s=0.5)
    with pytest.raises(ValueError):
        CreditsSnapshot(outcome=sp.OUTCOME_UNREADABLE, balance=None)


def test_both_credits_fields_are_touched_only_inside_the_lock():
    """The archive shipped these as two UNlocked statements and had to fix
    it: a reader landing between them pairs an OLD balance with a NEW
    timestamp, understating the age -- "where a falsely-fresh stale balance
    is a real over-spend defeat."

    Checked structurally because the race is not reproducible on demand.
    Every read and every write of the pair, in both methods, must sit inside
    a ``with self.lock:`` block -- one hold, both fields.
    """
    tree = ast.parse(SESSION_PATH.read_text(encoding="utf-8"))

    methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name in ("observe_credits", "credits_snapshot")
    }
    assert set(methods) == {"observe_credits", "credits_snapshot"}

    for name, func in methods.items():
        # Every `self.last_credits*` node anywhere in the method...
        touches = [
            node
            for node in ast.walk(func)
            if isinstance(node, ast.Attribute)
            and node.attr in ("last_credits", "last_credits_ts")
        ]
        assert len(touches) == 2, (name, len(touches))
        # ...and every one of them reachable only from inside a `with
        # self.lock:` block. Collected by walking the With bodies, so a
        # touch outside every hold simply will not appear in the set.
        guarded = set()
        for node in ast.walk(func):
            if not isinstance(node, ast.With):
                continue
            if not any(
                isinstance(item.context_expr, ast.Attribute)
                and item.context_expr.attr == "lock"
                for item in node.items
            ):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr in (
                    "last_credits",
                    "last_credits_ts",
                ):
                    guarded.add(id(inner))
        assert {id(t) for t in touches} <= guarded, f"{name} touches the pair outside the lock"


# ==========================================================================
# 3 -- the decision, branch by branch
# ==========================================================================
#
# `_check_floor` is pure, so every branch is reachable directly. That is the
# point of it being pure: a ladder only exercised through a scripted run is
# a ladder whose unreachable rungs nobody notices.


def _read(balance, age_s):
    return CreditsSnapshot(outcome=sp.OUTCOME_READ, balance=balance, age_s=age_s)


def test_an_unfloored_run_has_nothing_to_check():
    """`floor=None` returns immediately and does not look at credits at all
    -- including a credits value that would otherwise halt."""
    assert _check_floor(None, None, CREDITS_STALE_MS) is None
    assert _check_floor(sp.credits_never_observed(), None, CREDITS_STALE_MS) is None
    assert _check_floor(("garbage",), None, CREDITS_STALE_MS) is None


def test_an_unobserved_balance_halts_credits_unknown():
    """The headline. Canon: "an unknown or stale balance HALTs ... rather
    than arming an unbounded floor.\""""
    assert (
        _check_floor(sp.credits_never_observed(), 500, CREDITS_STALE_MS)
        == HALT_CREDITS_UNKNOWN
    )


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(None, id="port-returned-None"),
        pytest.param((500, 0.0), id="raw-balance-ts-pair"),
        pytest.param(("timeout", 8.0), id="settle-2-tuple"),
        pytest.param(("prompt", 0.4, False), id="settle-3-tuple"),
        pytest.param((None, None), id="never-observed-pair"),
        pytest.param(500, id="bare-int"),
        pytest.param({"balance": 500, "age_s": 0.0}, id="dict"),
        pytest.param(sp.CreditsRead(outcome=sp.OUTCOME_ABSENT), id="wrong-credits-type"),
    ],
)
def test_anything_that_is_not_a_snapshot_halts_rather_than_being_interpreted(answer):
    """THE TRUTHY-TUPLE PIN. Every tuple above is truthy -- ``("timeout",
    8.0)`` and ``("prompt", 0.4, False)`` are the settle layer's own return
    shapes and the obvious things a careless adapter forwards. A truthiness
    test would read each of them as a healthy balance and press on."""
    assert bool(answer) or answer is None  # the hazard, stated
    assert _check_floor(answer, 500, CREDITS_STALE_MS) == HALT_CREDITS_UNREADABLE


def test_the_freshness_window_is_a_real_boundary():
    """Computed either side of the limit rather than hand-typed, so IEEE-754
    rounding cannot make this test agree with a different threshold than the
    code's."""
    assert _check_floor(_read(10_000, STALE_S), 500, CREDITS_STALE_MS) is None
    assert _check_floor(_read(10_000, STALE_S - 0.001), 500, CREDITS_STALE_MS) is None
    assert (
        _check_floor(_read(10_000, STALE_S + 0.001), 500, CREDITS_STALE_MS)
        == HALT_CREDITS_STALE
    )
    # A stale balance halts even when it is comfortably ABOVE the floor --
    # that is the "a stale-but-still-above-floor reading masks a real
    # sub-floor balance" defeat, and it is the whole reason the freshness
    # gate sits before the comparison rather than after it.
    assert (
        _check_floor(_read(10_000_000, STALE_S * 4), 500, CREDITS_STALE_MS)
        == HALT_CREDITS_STALE
    )


def test_a_nan_age_is_caught_at_the_decision_too():
    """Belt AND braces. ``CreditsSnapshot`` rejects a NaN age at
    construction, so this builds one through ``object.__new__`` to reach the
    decision site directly -- because a defence that is only ever enforced by
    a sibling is not a property of this function."""
    rogue = object.__new__(CreditsSnapshot)
    object.__setattr__(rogue, "outcome", sp.OUTCOME_READ)
    object.__setattr__(rogue, "balance", 10_000)
    object.__setattr__(rogue, "age_s", float("nan"))
    assert math.isnan(rogue.age_s)
    # The naive ladder: `nan > limit` is False, i.e. "fresh".
    assert (rogue.age_s > STALE_S) is False
    assert _check_floor(rogue, 500, CREDITS_STALE_MS) == HALT_CREDITS_STALE


def test_the_floor_comparison_is_at_or_below():
    """The archived rail's own boundary (`bal <= floor` halts): a floor of
    500 means "stop at 500", not "stop below 500"."""
    assert _check_floor(_read(501, 0.0), 500, CREDITS_STALE_MS) is None
    assert _check_floor(_read(500, 0.0), 500, CREDITS_STALE_MS) == HALT_FLOOR_REACHED
    assert _check_floor(_read(499, 0.0), 500, CREDITS_STALE_MS) == HALT_FLOOR_REACHED
    assert _check_floor(_read(0, 0.0), 0, CREDITS_STALE_MS) == HALT_FLOOR_REACHED
    assert _check_floor(_read(1, 0.0), 0, CREDITS_STALE_MS) is None


def test_every_new_halt_code_is_in_the_closed_vocabulary():
    for code in (
        HALT_FLOOR_REACHED,
        HALT_CREDITS_UNKNOWN,
        HALT_CREDITS_STALE,
        HALT_CREDITS_UNREADABLE,
    ):
        assert code in HALT_REASONS


def test_which_of_the_new_codes_canon_already_has_a_label_for():
    """WO-HALT-BANNER-LABEL-VOCAB / Max 1A: floor_reached and
    credits_unreadable now carry human labels (they used to render RAW).
    credits_unknown / credits_stale were already labelled.
    """
    labels = stopbanner.INTERVENTION_REASON_LABELS
    assert labels[HALT_CREDITS_UNKNOWN] == "credits unknown"
    assert labels[HALT_CREDITS_STALE] == "credits stale"
    assert labels[HALT_FLOOR_REACHED] == "floor reached"
    assert labels[HALT_CREDITS_UNREADABLE] == "credits unreadable"

    for code, expected in (
        (HALT_FLOOR_REACHED, "floor reached"),
        (HALT_CREDITS_UNREADABLE, "credits unreadable"),
    ):
        status = {"intervention": {"needs_attention": True, "reasons": [{"code": code}]}}
        banner = "\n".join(
            stopbanner.compose_stop_banner_lines(status, width=120, height=3)
        )
        assert expected in banner, banner
        assert code not in banner, banner  # human label, not RAW identifier


# ==========================================================================
# 4 -- enforcement inside a real replay
# ==========================================================================


class CreditsScript:
    """A port that answers `credits()` from a script, one entry per
    boundary, and records that it was asked.

    Scripted rather than derived from the screen so the floor ladder is
    isolated from the parser: a test that halted because the fixture screen
    happened to state no balance would be proving the parser, not the rail.
    The parser and the wiring are proven together end-to-end in section 6.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = 0

    def next(self):
        self.asked += 1
        return self.answers.pop(0) if self.answers else self.answers_default

    answers_default = None


class FlooredSession(ScriptedSession):
    """X3's scripted port plus a `credits()`."""

    def __init__(self, screens, credits, **kwargs):
        super().__init__(screens, **kwargs)
        self._credits = CreditsScript(credits)

    def credits(self):
        self.calls.append("credits")
        return self._credits.next()


class FlooredNoSendSession(FlooredSession):
    """The zero-bytes instrument, floored. Reaching the wire IS the
    failure, and nothing about the reported reason is trusted by the tests
    that use it."""

    def send_and_confirm(self, keystrokes, wait_prompt):  # pragma: no cover
        raise AssertionError(
            f"the player sent {keystrokes!r} past its own credit floor -- a stop-loss "
            "that sends first and reports afterwards is not a stop-loss"
        )


class SendsOnceSession(FlooredSession):
    """Sends exactly once, then treats a second send as the failure.

    The mid-run instrument: a floor that only fires at launch would let
    step 1 through, and this is what makes "the NEXT send never happened" an
    assertion rather than an inference from `sends_issued`."""

    def send_and_confirm(self, keystrokes, wait_prompt):
        if self.sends:  # pragma: no cover - must not run
            raise AssertionError(
                f"the player sent {keystrokes!r} after the balance crossed the floor"
            )
        return super().send_and_confirm(keystrokes, wait_prompt)


HEALTHY = _read(10_000, 0.0)
BROKE = _read(400, 0.0)
STALE = _read(10_000, STALE_S * 3)
UNOBSERVED = sp.credits_never_observed()

ONE_STEP_LOOP = make_loop([("P", None, "main_command")])
TWO_STEP_LOOP = make_loop(
    [("P", None, "main_command"), ("Q", None, "main_command")]
)
CLEAN_SCREENS = [ANCHOR_158, ANCHOR_158, ANCHOR_158]


def test_a_run_with_no_floor_never_asks_for_credits():
    """The archive's own rule, kept because it is what lets every port
    written before this parameter existed keep working -- and what makes "a
    floor was requested" and "credits were consulted" the same event."""
    session = FlooredSession(CLEAN_SCREENS, [])
    result = replay_loop(ONE_STEP_LOOP, session)
    assert result.outcome == OUTCOME_COMPLETED
    assert session._credits.asked == 0
    assert "credits" not in session.calls


def test_the_same_scenario_completes_when_the_balance_clears_the_floor():
    """THE POSITIVE CONTROL. Every halt below runs on these exact fixtures
    with only the balance changed, so a halt cannot be attributed to the
    screen, the anchor, the classification, or the port."""
    session = FlooredSession(CLEAN_SCREENS, [HEALTHY, HEALTHY])
    result = replay_loop(ONE_STEP_LOOP, session, floor=500)
    assert result.outcome == OUTCOME_COMPLETED
    assert result.reason is None
    assert session.sends == [("P", None)]
    assert session._credits.asked == 2  # boundary 0 and boundary 1


@pytest.mark.parametrize(
    "answer,expected",
    [
        pytest.param(UNOBSERVED, HALT_CREDITS_UNKNOWN, id="never-observed"),
        pytest.param(STALE, HALT_CREDITS_STALE, id="too-old"),
        pytest.param(BROKE, HALT_FLOOR_REACHED, id="at-or-below-floor"),
        pytest.param((10_000, 0.0), HALT_CREDITS_UNREADABLE, id="raw-tuple"),
        pytest.param(None, HALT_CREDITS_UNREADABLE, id="nothing"),
    ],
)
def test_boundary_zero_halts_before_a_single_byte(answer, expected):
    """The fail-closed headline, proven by a port whose send RAISES.

    Note the screen: `ANCHOR_158` classifies `main_command`, matches the
    macro's anchor, is not fenced and is not aborted -- so no other guard
    can fire, and the halt is genuinely the floor's. (The positive control
    above completes on the identical fixtures.)
    """
    session = FlooredNoSendSession(CLEAN_SCREENS, [answer])
    result = replay_loop(ONE_STEP_LOOP, session, floor=500)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == expected
    assert result.halted_at == player_mod.BEFORE_FIRST_SEND
    assert result.sends_issued == 0
    assert session.sends == []


@pytest.mark.parametrize(
    "answer,expected",
    [
        pytest.param(UNOBSERVED, HALT_CREDITS_UNKNOWN, id="never-observed"),
        pytest.param(STALE, HALT_CREDITS_STALE, id="too-old"),
        pytest.param(BROKE, HALT_FLOOR_REACHED, id="at-or-below-floor"),
        pytest.param(("timeout", 8.0), HALT_CREDITS_UNREADABLE, id="settle-tuple"),
    ],
)
def test_the_floor_is_re_checked_before_every_send_not_only_at_launch(answer, expected):
    """The difference between a stop-loss and a decoration.

    Boundary 0 is healthy so the run genuinely starts and step 0 genuinely
    sends -- then the balance goes bad and step 1 must never reach the wire.
    A once-at-launch floor passes every boundary-0 test above and fails this
    one, which is exactly why it is here.
    """
    session = SendsOnceSession(CLEAN_SCREENS, [HEALTHY, answer])
    result = replay_loop(TWO_STEP_LOOP, session, floor=500)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == expected
    assert result.halted_at == 0  # halted AT step 0's boundary; step 1 never sent
    assert result.sends_issued == 1
    assert session.sends == [("P", None)]


def test_the_final_boundary_is_checked_too_and_a_broke_run_does_not_report_completed():
    """The last boundary has no send after it, and it is checked anyway --
    the same treatment every other guard already gets there.

    "The run finished, and it finished below your floor" is not a completed
    run from the operator's side, and a rail that fell silent on the last
    boundary would report exactly that. (This is the shape of the reporting,
    not a claim that a send was prevented -- there was none left to prevent.)
    """
    session = FlooredSession(CLEAN_SCREENS, [HEALTHY, BROKE])
    result = replay_loop(ONE_STEP_LOOP, session, floor=500)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == HALT_FLOOR_REACHED
    assert result.sends_issued == 1
    assert session.sends == [("P", None)]


def test_credits_are_read_after_the_screen_at_every_boundary():
    """Ordering, pinned. An adapter captures the balance off the render
    `screen()` takes, so asking for credits FIRST would answer from the
    previous boundary -- a reading from before the send this boundary is
    about to gate."""
    session = FlooredSession(CLEAN_SCREENS, [HEALTHY, HEALTHY])
    replay_loop(ONE_STEP_LOOP, session, floor=500)
    boundary = ["settle", "screen", "credits", "is_driver_fenced", "should_abort"]
    assert session.calls == boundary + ["send_and_confirm"] + boundary


def test_a_more_sovereign_guard_outranks_the_floor_and_the_floor_still_bites():
    """Isolation, both directions -- the X3 vacuity lesson applied to this
    rail.

    Same below-floor balance in both halves. With a human at the keyboard
    the operator is told about the HUMAN, because that is the more sovereign
    fact; with the keyboard free they are told about the MONEY. If the floor
    branch were dead, the first half would still pass -- which is precisely
    the shape of "13 of 16 cells passing because a different guard fired".
    """
    fenced = FlooredNoSendSession(CLEAN_SCREENS, [BROKE], fences=[True])
    assert replay_loop(ONE_STEP_LOOP, fenced, floor=500).reason == HALT_FENCED

    aborted = FlooredNoSendSession(CLEAN_SCREENS, [BROKE], aborts=[True])
    assert replay_loop(ONE_STEP_LOOP, aborted, floor=500).reason == HALT_ABORTED

    clean = FlooredNoSendSession(CLEAN_SCREENS, [BROKE])
    assert replay_loop(ONE_STEP_LOOP, clean, floor=500).reason == HALT_FLOOR_REACHED


def test_a_money_screen_is_still_refused_under_a_healthy_floor():
    """The floor does not become a substitute for the never-auto guard, and
    a healthy balance does not license a money prompt. Both rails, one
    boundary."""
    session = FlooredNoSendSession([MONEY, MONEY], [HEALTHY])
    result = replay_loop(ONE_STEP_LOOP, session, floor=500)
    assert result.reason == "never_auto_action:money_prompt"
    assert session.sends == []


@pytest.mark.parametrize(
    "answer,expected",
    [
        pytest.param(UNOBSERVED, HALT_CREDITS_UNKNOWN, id="never-observed"),
        pytest.param(STALE, HALT_CREDITS_STALE, id="too-old"),
        pytest.param(BROKE, HALT_FLOOR_REACHED, id="at-or-below-floor"),
        pytest.param(None, HALT_CREDITS_UNREADABLE, id="unreadable"),
    ],
)
def test_force_waives_no_floor_halt(answer, expected):
    """`force` waives exactly one thing -- a macro with no recorded anchor.
    A credit floor is not a recording artifact, it is live money, and there
    is nothing about it that "there was nothing to check against" could
    describe. Run with an ANCHORLESS macro so `force` is genuinely doing its
    one job at the same boundary."""
    loop = make_loop([("P", None, "main_command")], start_anchor=None)
    session = FlooredNoSendSession(CLEAN_SCREENS, [answer])
    result = replay_loop(loop, session, floor=500, force=True)
    assert result.reason == expected
    assert session.sends == []
    assert expected not in player_mod.FORCEABLE_HALTS


def test_a_floor_handed_to_a_port_that_cannot_observe_credits_is_refused_at_entry():
    """Zero bytes AND zero observations: the refusal happens before the
    first settle, so a driver that wired a floor without wiring the port
    finds out from a message rather than from an ``AttributeError`` at the
    first boundary.

    This is the API-level half of "never accept a floor you cannot enforce".
    """
    session = ScriptedSession(CLEAN_SCREENS)  # X3's port -- no `credits()`
    assert not hasattr(session, "credits")
    with pytest.raises(TypeError, match="cannot observe credits"):
        replay_loop(ONE_STEP_LOOP, session, floor=500)
    assert session.calls == []
    assert session.sends == []

    # ...and the same port is perfectly usable with no floor.
    assert replay_loop(ONE_STEP_LOOP, session).outcome == OUTCOME_COMPLETED


@pytest.mark.parametrize("bad", [True, False, 500.0, "500", object()])
def test_a_floor_that_is_not_an_int_is_refused_at_entry(bad):
    """`True` is an int in Python and would arm a floor of 1; a float would
    compare fine and never be the number anyone typed."""
    session = FlooredNoSendSession(CLEAN_SCREENS, [HEALTHY])
    with pytest.raises(TypeError, match="must be an int"):
        replay_loop(ONE_STEP_LOOP, session, floor=bad)
    assert session.calls == []


@pytest.mark.parametrize("bad", [0, -1])
def test_a_window_that_never_expires_is_refused(bad):
    session = FlooredNoSendSession(CLEAN_SCREENS, [HEALTHY])
    with pytest.raises(ValueError, match="must be positive"):
        replay_loop(ONE_STEP_LOOP, session, floor=500, credits_stale_ms=bad)
    assert session.calls == []


# ==========================================================================
# 5 -- the injection: build the cheat, watch the pin go red
# ==========================================================================


_variant_serial = itertools.count()


def _variant(source: str) -> types.ModuleType:
    """Execute a mutated copy of ``player.py`` as a real module.

    ``__package__`` is set so the module's relative imports resolve against
    the real package, and the module is registered in ``sys.modules`` before
    the exec because ``@dataclass`` resolves annotations through
    ``sys.modules[cls.__module__]`` at class-creation time -- an unregistered
    module makes ``ReplayResult`` fail to build, which would look like the
    injection working when it had not even loaded.

    The variant differs from the shipped module in exactly the mutation and
    in nothing else.
    """
    name = f"tw2002_aiclient.loops._player_under_injection_{next(_variant_serial)}"
    module = types.ModuleType(name)
    module.__package__ = "tw2002_aiclient.loops"
    module.__file__ = str(PLAYER_PATH)
    sys.modules[name] = module
    try:
        exec(compile(source, str(PLAYER_PATH), "exec"), module.__dict__)
    except BaseException:  # pragma: no cover - a broken mutation must not linger
        sys.modules.pop(name, None)
        raise
    return module


def _replace_once(source: str, old: str, new: str) -> str:
    """Textual mutation with the anchor asserted present exactly once, so a
    refactor that moved the line makes this test fail loudly instead of
    silently injecting nothing and reporting a pass."""
    assert source.count(old) == 1, f"anchor not unique ({source.count(old)}): {old!r}"
    return source.replace(old, new)


def _cheat_neuter_the_decision() -> types.ModuleType:
    """THE CHEAT, in its purest form: accept the floor, never decide on it.
    ``_check_floor`` keeps its name, its signature, its docstring and its
    call sites -- and returns ``None`` for everything."""
    tree = ast.parse(PLAYER_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_check_floor":
            docstring = node.body[0]
            node.body = [docstring, ast.parse("return None").body[0]]
            break
    else:  # pragma: no cover
        raise AssertionError("_check_floor is gone -- this injection is measuring nothing")
    return _variant(ast.unparse(ast.fix_missing_locations(tree)))


def _cheat_cut_the_call_sites() -> types.ModuleType:
    """The other shape of the same cheat: keep a perfectly good decision
    function and simply never call it. A floor that is parsed, stored, and
    reported on the run record -- and checked nowhere."""
    source = PLAYER_SRC
    call = "reason = _check_floor(observation.credits, floor, credits_stale_ms)"
    assert source.count(call) == 2, source.count(call)
    return _variant(source.replace(call, "reason = None"))


def _cheat_unknown_means_fine() -> types.ModuleType:
    """The subtle one, and the one a green suite is most likely to ship: the
    floor is checked, the comparison is real, and an unobservable balance
    quietly proceeds. Canon's sentence exists because of exactly this: "an
    unknown or stale balance HALTs ... rather than arming an unbounded
    floor.\""""
    return _variant(
        _replace_once(PLAYER_SRC, "return HALT_CREDITS_UNKNOWN", "return None")
    )


def _the_floor_scenario(module, answer):
    """The scenario :func:`test_boundary_zero_halts_before_a_single_byte`
    asserts on, run against an arbitrary build of the player."""
    session = FlooredNoSendSession(CLEAN_SCREENS, [answer])
    result = module.replay_loop(ONE_STEP_LOOP, session, floor=500)
    assert result.sends_issued == 0
    assert session.sends == []
    return result


def test_the_shipped_module_passes_the_scenario_the_cheats_are_run_through():
    """Stated separately so the injections below are comparing against a
    known-passing baseline rather than against an assumption."""
    assert _the_floor_scenario(player_mod, BROKE).reason == HALT_FLOOR_REACHED
    assert _the_floor_scenario(player_mod, UNOBSERVED).reason == HALT_CREDITS_UNKNOWN


@pytest.mark.parametrize(
    "build_cheat,answer",
    [
        pytest.param(_cheat_neuter_the_decision, BROKE, id="decision-neutered"),
        pytest.param(_cheat_cut_the_call_sites, BROKE, id="call-sites-cut"),
        pytest.param(_cheat_unknown_means_fine, UNOBSERVED, id="unknown-means-fine"),
    ],
)
def test_injecting_the_cheat_turns_the_guard_test_red(build_cheat, answer):
    """RED-FIRST, after the fact and on purpose.

    Each cheat is applied to the real module source and run through the
    *same* scenario the passing test above asserts on. The scenario's own
    zero-bytes instrument is what fires: ``FlooredNoSendSession`` raises the
    moment a keystroke is issued past the floor.

    If any of these did NOT raise, the pin above it would be measuring
    nothing -- a floor accepted and never enforced would ship green.
    """
    cheat = build_cheat()
    with pytest.raises(AssertionError, match="past its own credit floor"):
        _the_floor_scenario(cheat, answer)


def test_the_cheats_differ_from_the_shipped_module_in_exactly_the_cheat():
    """A mutation that failed to apply would make the test above pass for
    the wrong reason -- so each variant is checked to be a DIFFERENT module
    that still behaves identically on an unfloored run."""
    for build_cheat in (
        _cheat_neuter_the_decision,
        _cheat_cut_the_call_sites,
        _cheat_unknown_means_fine,
    ):
        cheat = build_cheat()
        assert cheat is not player_mod
        session = FlooredSession(CLEAN_SCREENS, [])
        assert cheat.replay_loop(ONE_STEP_LOOP, session).outcome == OUTCOME_COMPLETED
        assert session._credits.asked == 0


# ==========================================================================
# 6 -- the daemon, end to end through the real verbs
# ==========================================================================


class CreditsWireSession(WireSession):
    """X4's fake wire, with the REAL credits methods bound off ``Session``.

    Assigned off the class rather than reimplemented (the convention this
    repo's fakes already use for exactly this) so these tests exercise the
    same locking, the same strict parser, and the same non-clobber rule a
    real daemon does -- a reimplementation here would let the fake and the
    product drift on the one contract under test.
    """

    observe_credits = Session.observe_credits
    credits_snapshot = Session.credits_snapshot

    def __init__(self, screens, **kwargs):
        super().__init__(screens, **kwargs)
        # `FakeAttachSession` pre-seeds a sticky balance for an unrelated
        # HUD fixture; a stop-loss test must start from a session that has
        # genuinely observed nothing, or "unknown" would never be under test.
        self.last_credits = None
        self.last_credits_ts = None


def _screens(*bodies):
    return [_screen_with(body) for body in bodies]


def test_the_wire_accepts_a_floor_and_the_report_carries_the_number(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession(_screens(BALANCE_AFTER, BALANCE_AFTER))
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "floor": 500}, server
    )
    assert resp["ok"] is True
    assert resp["run"]["floor"] == 500
    run_to_completion(server.autoloop, session)

    status = protocol.dispatch(session, "autoloop_status", {}, server)
    assert status["run"]["floor"] == 500
    assert status["run"]["outcome"] == "completed"
    # The balance really did travel: parser -> observe_credits -> snapshot.
    assert session.credits_snapshot().balance == 100485


def test_an_unfloored_run_reports_a_null_floor(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    assert resp["run"]["floor"] is None
    run_to_completion(server.autoloop, session)
    assert protocol.dispatch(session, "autoloop_status", {}, server)["run"][
        "outcome"
    ] == "completed"


def test_a_floored_run_with_no_balance_in_sight_halts_and_the_banner_says_so(tmp_path):
    """Canon's arm-confirm rail, end to end: "the arm sequence must have
    shown a confirmed balance before a floored run will start, or a
    legitimate run instant-dies rather than arming blind."

    The screens here are ordinary command prompts -- they state no balance,
    so nothing is ever observed, so the run dies at boundary 0 having sent
    nothing. The assertion is on the rendered STOP banner rather than on the
    status dict, because the code reaching the operator is the thing that
    matters.
    """
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "floor": 500}, server
    )
    assert resp["ok"] is True
    run_to_completion(server.autoloop, session)

    status = protocol.dispatch(session, "status", {}, server)
    assert stopbanner.needs_attention(status) is True
    banner = "\n".join(stopbanner.compose_stop_banner_lines(status, width=120, height=3))
    assert "credits unknown" in banner

    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "halted"
    assert run["reason"] == HALT_CREDITS_UNKNOWN
    assert run["sends_issued"] == 0
    assert session.sent == []
    assert lock.is_auto_loop_held() is False


def test_a_floored_run_halts_when_the_live_screen_shows_a_sub_floor_balance(tmp_path):
    """The whole chain, on real text: a real screen states a real balance, a
    real strict parser reads it, the real sticky store ages it, and the real
    rail refuses the send. Nothing here is scripted at the credits layer."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession(_screens("You have 400 credits.", BALANCE_AFTER))
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    protocol.dispatch(session, "autoloop_start", {"name": "ore-run", "floor": 500}, server)
    run_to_completion(server.autoloop, session)

    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "halted"
    assert run["reason"] == HALT_FLOOR_REACHED
    assert run["sends_issued"] == 0
    assert session.sent == []


def test_a_human_do_establishes_the_balance_a_later_floored_run_needs(tmp_path):
    """The other capture point, and the one that makes a floored run usable
    at all: a human flying by hand passes through ``build_response``, which
    is where the arm-confirm precondition actually gets satisfied.

    Without this leg, a floored run could only ever start from a screen that
    happened to be stating a balance -- enforced, but not usable, which is
    its own kind of dishonest.
    """
    write_macro(tmp_path, "ore-run", ONE_STEP)
    # The run's own screens state NO balance at all, so the only possible
    # source is the human's earlier look.
    session = CreditsWireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    assert session.credits_snapshot().outcome == sp.OUTCOME_ABSENT
    session._screen = _screen_with(BALANCE_AFTER)
    protocol.dispatch(session, "status", {}, server)  # the human looks
    assert session.credits_snapshot().balance == 100485
    session._screen = ANCHOR_158[0]

    protocol.dispatch(session, "autoloop_start", {"name": "ore-run", "floor": 500}, server)
    run_to_completion(server.autoloop, session)

    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "completed", run
    assert session.sent  # it really did fly


@pytest.mark.parametrize("bad", [True, False, 500.0, "500"])
def test_a_floor_of_the_wrong_shape_is_refused_at_the_wire(tmp_path, bad):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "floor": bad}, server
    )
    assert resp == {"ok": False, "error": "invalid_floor"}
    assert lock.is_auto_loop_held() is False
    assert session.sent == []


def test_a_negative_floor_is_refused(tmp_path):
    """A floor that can never be crossed is a stop-loss that structurally
    cannot stop -- the decorative flag this slice forbids, wearing a
    number."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "floor": -1}, server
    )
    assert resp == {"ok": False, "error": "invalid_floor"}
    assert lock.is_auto_loop_held() is False


def test_repetition_is_accepted_with_floor(tmp_path):
    """WO-AUTOLOOP-CYCLES: cycles + floor together are a legal arm."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = CreditsWireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "cycles": 2, "floor": 500}, server
    )
    assert resp["ok"] is True
    assert resp["run"]["cycles"] == 2
    assert resp["run"]["floor"] == 500
    server.autoloop.stop()


def test_the_arg_vocabulary_grew_by_exactly_the_enforced_rails(tmp_path):
    """Pinned as a set rather than as a count, so a future arg has to be
    argued for here as well as wired."""
    assert autoloop.ARGS_AUTOLOOP_START == frozenset(
        {"name", "floor", "turn_budget", "cycles"}
    )


def test_the_port_forwards_the_snapshot_whole(tmp_path):
    """The adapter's own contract: no unpacking, no age computed in the
    port, no `(balance, ts)` pair. The player isinstance-checks this, and a
    flattened answer would halt `credits_unreadable` -- but it would also be
    a lie about what the session said, so it is pinned here directly."""
    session = CreditsWireSession(_screens(BALANCE_AFTER))
    port = autoloop._ReplayPort(session, ControlLock(), threading.Event())
    assert isinstance(port.credits(), CreditsSnapshot)
    assert port.credits().outcome == sp.OUTCOME_ABSENT  # nothing rendered yet

    port.screen()  # the capture point
    snapshot = port.credits()
    assert isinstance(snapshot, CreditsSnapshot)
    assert snapshot.balance == 100485
