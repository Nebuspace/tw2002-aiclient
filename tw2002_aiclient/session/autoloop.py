"""The daemon's background loop player -- and the only thing in this
package that calls ``ControlLock.enter_auto_loop()``.

WO-P2-G4-X4. ``loops/player.py`` (X3) decides whether a keystroke may be
pressed; this module is what hands it a real socket, a real control lock,
and a thread to run on, and what answers the operator afterwards. It adds
no guard of its own and removes none: every refusal in a run below comes
out of the player, in the player's own closed vocabulary.

Canon
-----
* ``canon/architecture/app-autopilot-model.md`` §"Background AUTO-LOOP
  Posture" is the posture this implements: human-armed ("it can never
  read as 'on' without an actually-running driver thread behind it"),
  stop-on-unknown mid-loop, and "stops itself the moment the human takes
  the keyboard".
* Same doc §"Arm-Confirm": the arm gate is "a **required, external
  input** to the loop, not an internal self-check the loop could grant
  itself", and a disarm "reaches an in-flight run within one step".
* ``canon/doctrine/action-safety-guards.md`` §"Structural rails" names
  the rails a *repeating* loop owes -- turn-budget, stop-loss,
  hazard-halt, novelty-halt, arm-confirm. See "One pass" below for which
  of them this slice is and is not entitled to claim.
* ``canon/architecture/control-and-escalation.md`` §"Escalation
  reason-code catalog": a STOP carries a typed code, "not a free-text
  string", and surfaces render the code. That is why the halt reason
  travels to ``status`` unmodified.

The arm state is the safety surface
-----------------------------------
``cockpit/arm.py`` shipped read-only with no setter, because a write path
"would render ``ARM ON`` for a runtime that cannot arm: a fabricated
affirmative safety claim". This module is the runtime that can now arm,
so the chip has to become TRUE, not merely non-blank. Two states are
forbidden, and neither is reachable here:

* **armed while nothing is running.** ``running`` is never a stored
  claim. It is computed, per read, as ``in_flight or <the exclusive App
  hold is held>`` -- so it can only be ``True`` while either a run
  thread is between ``start()`` and its own ``finally``, or the App
  actually holds the one connection. Both are "something is running" in
  the only sense an operator cares about: the App has the wire.
* **unarmed while the player holds the lock.** Structurally impossible,
  because the hold is one of the two disjuncts. There is no branch to
  get wrong: any state that holds the lock reports armed.

Both facts are read under ONE mutex hold (:meth:`AutoLoopRunner.snapshot`
takes ``_mutex`` and asks the control lock from inside it), and the run
thread publishes its own end-of-run transition -- release the hold, write
the report, clear ``in_flight`` -- inside that same mutex. So there is no
window in which a reader can see half of a transition: an observation is
either wholly before or wholly after. A caller that read ``in_flight``
and the lock through two separate calls could interleave between them,
which is exactly why :func:`observe` exists and why ``protocol.py`` has
no second path to these two facts.

One release path, and it belongs to the run
-------------------------------------------
``leave_auto_loop()`` is called from exactly one place: the ``finally``
of :meth:`AutoLoopRunner._run`. ``stop()`` does NOT release, and that is
deliberate rather than an oversight. A stop that released the hold itself
would drop the App's exclusivity while the run was still mid-step, and a
``do``/``send`` arriving in that window would interleave a second driver
on the one wire -- the precise failure the exclusive hold exists to
prevent. So ``stop()`` only *requests*, through the player's arm
predicate, and the run releases as it dies, within one send-step.

The fence wiring, a trap in it, and the trap's later repair
-------------------------------------------------------------
The player asks its port ``is_driver_fenced()`` at every boundary. When
this module landed (X4, commit ``344991e``), forwarding
``ControlLock.is_driver_fenced()`` was WRONG, and quietly so: that flag
was only raised by ``take_human()`` when an App *dispatch* held the
driver slot (``_driving``); a background run holds ``enter_auto_loop()``
instead, so ``_driving`` stayed ``False`` and the flag stayed down. An
adapter forwarding it would have answered "not fenced" while a human
typed into the game, and the player would have kept pressing keys.

**WO-CONTROL-LOCK-AUTOLOOP-FENCE fixed that flag itself** -- ``take_human()``
now fences an auto_loop preemption too (each preempted generation added to
its own set, ``_auto_loop_fenced_generations``, whose non-emptiness is
OR'd into ``is_driver_fenced()``), so ``ControlLock.is_driver_fenced()`` is
honest for this case as of that WO.
That fix was for a DIFFERENT caller, though: ``Session.send_raw``'s bounded
wind-down wait on the human-attach keystroke path, which had no fence
signal for an auto_loop preemption at all before it. It was never a fix to
THIS predicate, because this predicate was never wrong about what it
answers -- only about which lock field would have been an honest source
for it.

The port's own predicate below is kept exactly as it was: the run's own
authority, *is the hold I took still mine?*, read off ``is_auto_loop_held()``
directly rather than off ``ControlLock.is_driver_fenced()`` even now that
the latter is honest for this case too. The two are provably equivalent
today (both flip on take_human()'s SAME preemption, in the same critical
section, for the entire window this port is actually asked); reasoned
through, not merely asserted, because the equivalence rests on invariants
(the mutual exclusion between ``_driving`` and ``_auto_loop_held``,
``leave_auto_loop()``'s single call site, this port's one-run lifetime)
that a future change could quietly break without a dispatch-fence test
noticing. Simplifying this port to forward ``control_lock.
is_driver_fenced()`` was considered and declined -- kept independent
instead.

**That independence was called "defense in depth" in an earlier pass of
this WO. That framing was incomplete, and the retraction is recorded
here rather than silently corrected.** Cipher's later finding (round 5):
``is_auto_loop_held()`` answers *"is some hold currently standing"*, not
*"is MY generation's hold still standing"* -- it carries no generation
parameter at all, structurally the SAME shape as the original single-bool
fence defect this WO exists to fix. It reads correctly today for the
identical reason the fence's >1 cardinality is unreachable today (see
``control_lock.py``'s closing module-docstring note): ``AutoLoopRunner``
never lets a second generation's thread exist while this port's own run
is still alive, so "some hold is standing" and "MY hold is standing" can
never come apart while this predicate is actually asked. **A second path
to the same halt is only genuine defense in depth if it does not share
the defect the first path had** -- this one does, merely hidden behind
the same external serialization the rest of this WO had to make explicit
elsewhere. Recorded for ``WO-WEDGED-SEND-FENCE-STICKS`` (which exists to
REMOVE that very serialization, and would reopen this exact hazard
through the player layer if it did so without also fixing this port) --
not fixed here, because this WO's scope is the lock, not the player.

(Pinned by ``tests/test_autoloop.py``'s attach test, updated by the same
WO to assert the now-CORRECTED direction: the lock's own
``is_driver_fenced()`` is ``True`` at the moment of the halt, not the
stale ``False`` the original pin recorded as the trap.)

One pass, and why there is STILL no ``cycles``
----------------------------------------------
A ``start`` runs ONE pass of one taught macro and stops. X5 landed the
stop-loss floor, which was one of the four rails canon names for a
*repeating* surface (``action-safety-guards.md`` §"Structural rails") --
and it is deliberately NOT the thing that unlocks repetition, because it
is one rail and not the set. Standing today:

* **stop-loss** -- built (below, and enforced at the player's send
  choke-point).
* **novelty-halt** -- built (X3 halts on the first unrecognized frame).
* **turn-budget** -- NOT built. There is no turns observation in this tree
  at all, so canon's "a run whose turn budget is *unknown* fails closed"
  has nothing to read.
* **hazard-halt** -- NOT built. Zero-fighter state, an unrecoverable
  game-select, and a never-safe-to-proceed settle-desync are all
  unimplemented.

Two of four is not a set of rails; shipping N cycles on it would ship the
dangerous half of repetition just as surely as shipping it on none. When
the remaining two land, N cycles is N invocations of ``replay_loop`` and
gets canon's per-cycle start-anchor re-check for free -- which is
precisely why X3 refused a ``cycles`` parameter and why this module does
not smuggle one in as a ``for`` loop.

The consequence for the wire is stated rather than hidden: ``cycles``,
``force`` and ``param`` are **refused**, not ignored. A caller that asks
for ten cycles and gets one has been lied to by a surface that looked like
it agreed. ``floor`` is the one that changed sides, and only because the
thing behind it changed: X4 refused it precisely because "accepting a
credit floor that nothing enforces" is that same lie with money attached,
and it is accepted here **only** now that a floored run genuinely observes
credits, re-checks them before every send, and halts fail-closed when it
cannot. A ``floor`` this daemon could not enforce is still refused -- see
:meth:`AutoLoopRunner.start`, which will not arm one against a session
that cannot answer ``credits_snapshot()``. (``ensure``'s ``no_auto_arm``
is accepted-and-unused for a third reason: the behaviour it asks for --
never auto-arm -- is exactly what happens.)

What leaves this module
-----------------------
Nothing derived from the receive buffer, and no server-side path. A run
report carries the loop's own name (the caller supplied it), a closed
outcome vocabulary, the player's closed halt vocabulary, integers, and
timestamps. A loader failure reports its typed cause and the requested
name -- never the ``LoopMalformed.path`` it found, because that is
server-side filesystem layout the client never supplied (the leak
``daemon.py``'s ``internal_error:{type}`` narrowing was written for), and
never a step's recorded keystrokes. An exception from the player reports
its TYPE NAME on the wire and its traceback to the daemon's local error
log, for the same reason and by the same split.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Optional

from ..loops.loader import (
    LoopAmbiguous,
    LoopMalformed,
    LoopNotFound,
    LoopUnreadable,
    load_loop,
)
from ..loops.player import OUTCOME_HALTED, replay_loop
from . import settle as _settle
from .control_lock import ControlModeConflict
from .settle import MATCH_SCOPE_PROMPT_LINE

__all__ = [
    "ARGS_AUTOLOOP_START",
    "AutoLoopRefused",
    "AutoLoopRunner",
    "AutoLoopSnapshot",
    "OUTCOME_CRASHED",
    "REASON_PLAYER_ERROR",
    "RunReport",
    "arm_block",
    "intervention_block",
    "observe",
    "run_wire",
]


# The player's two outcomes plus one this module owns: the player itself
# raised, so there is no ReplayResult and no outcome to report from it.
# Kept distinct from `halted` because a halt is the system working.
OUTCOME_CRASHED = "crashed"

# The reason code that accompanies OUTCOME_CRASHED. A bare code, not
# `player_error:<Type>`, so the reason vocabulary a STOP banner renders
# stays a vocabulary; the type name rides its own `error` field.
REASON_PLAYER_ERROR = "player_error"

# Settle budgets for the port. The same numbers `do` uses (protocol.py),
# because a replay step is a drive send and there is no argument for
# holding a taught macro to a different standard than a hand-typed one.
SETTLE_TIMEOUT_S = 8.0
SETTLE_DEBOUNCE_MS = 350

# How long `stop` waits for the run to actually die before answering.
# Bounded rather than unbounded: a boundary can legitimately spend a
# settle budget plus a confirm budget, and a verb that blocked for the
# worst case would look like a wedged daemon. On expiry the answer is
# `running: true` -- honest, and the operator can ask again.
STOP_JOIN_TIMEOUT_S = 5.0

# The complete arg vocabulary of `autoloop_start`. Anything else is
# refused; see "One pass" in the module docstring for why silence would
# be the dishonest option. `floor` is here because X5 built the rail
# behind it -- an arg earns a place in this set by being enforced, never
# by being plausible.
ARGS_AUTOLOOP_START = frozenset({"name", "floor"})


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _can_observe_credits(session) -> bool:
    """Can this session answer the stop-loss's one question?

    Both halves are required and neither implies the other: ``observe_
    credits`` is what fills the sticky balance and ``credits_snapshot`` is
    what reads it back. A session with only the reader would answer
    ``absent`` forever -- fail-closed, but a run that instant-dies every
    time is worse than a refusal that says why, and canon's arm-confirm
    rail asks for exactly that ("preconditions unconfirmed => instant-die,
    never arm blind").

    ``callable`` rather than ``hasattr``: an attribute that exists and is
    not a function would pass a presence check and then raise at the first
    boundary, which is the failure this gate exists to move earlier."""
    return callable(getattr(session, "observe_credits", None)) and callable(
        getattr(session, "credits_snapshot", None)
    )


def _lock_held(control_lock) -> bool:
    """Does the exclusive App hold stand? ``getattr``-guarded exactly like
    ``protocol._control_lock_error``, so a bare test harness with no lock
    (or a double that predates the method) reports "not held" rather than
    crashing a status read."""
    probe = getattr(control_lock, "is_auto_loop_held", None)
    if probe is None:
        return False
    return bool(probe())


class AutoLoopRefused(Exception):
    """A start/stop that will not happen, carrying the typed code the wire
    reports. Never a free-text explanation: ``protocol.py`` puts
    ``str(exc)`` straight into an ``error`` field, so the message IS the
    vocabulary."""


class AutoLoopInvariantViolation(Exception):
    """Not a refusal -- a bug report. Deliberately NOT an
    :class:`AutoLoopRefused` (``protocol.py``'s ``except autoloop.
    AutoLoopRefused`` must NOT catch this): a refusal is an expected,
    named outcome a client can act on (``already_running``,
    ``loop_not_found:x``); this is ``AutoLoopRunner.start()`` discovering
    that an invariant EXTERNAL to this class -- "at most one auto_loop
    generation is ever outstanding" -- has already been violated before
    it even asked ``enter_auto_loop()`` for a new one. Left uncaught here,
    it propagates to ``daemon.py``'s outermost dispatch catch and reaches
    the wire as ``internal_error:AutoLoopInvariantViolation`` with a full
    traceback in the local log -- loud on purpose, not a bare ``assert``
    a ``-O`` run would silently strip, and not folded into the ordinary
    refusal vocabulary where it would read as just another polite
    no-thanks."""


# ---------------------------------------------------------------------------
# What a run reports
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunReport:
    """One run of one macro, in flight or finished.

    ``outcome is None`` means still running -- the one state where the
    other result fields are genuinely not known yet. They are ``None``
    rather than zero for the same reason ``sends_issued`` is ``None``
    after a crash: ``0`` is an affirmative claim that nothing reached the
    wire, and this module must never make that claim without the player's
    own count behind it.
    """

    loop: str
    started_at: str
    outcome: Optional[str] = None
    reason: Optional[str] = None
    halted_at: Optional[int] = None
    sends_issued: Optional[int] = None
    error: Optional[str] = None
    stop_requested: bool = False
    finished_at: Optional[str] = None
    # The floor this run was armed with, or `None` for an unfloored run.
    # Reported rather than kept private because "is a stop-loss actually
    # in force, and at what number" is a question an operator watching a
    # money-path run has to be able to answer from the surface -- and
    # because a floor that is invisible on the report is indistinguishable
    # from one that was silently dropped.
    floor: Optional[int] = None

    @property
    def halted(self) -> bool:
        """A finished run that did not complete -- the two outcomes a STOP
        banner exists for. ``crashed`` counts: a run whose driver raised
        also ended without doing what it was asked, and the operator needs
        to know that as much as they need to know about a guard-STOP."""
        return self.outcome in (OUTCOME_HALTED, OUTCOME_CRASHED)


@dataclass(frozen=True)
class AutoLoopSnapshot:
    """The two facts a surface needs, captured together.

    Together is the point: ``running`` and ``report`` read one at a time
    can straddle a run's end. Everything downstream is a pure function of
    this value, so no composer can re-read a moving runtime."""

    running: bool
    report: Optional[RunReport] = None


# ---------------------------------------------------------------------------
# Pure composers (no runtime access -- same discipline as cockpit/*.py)
# ---------------------------------------------------------------------------


def arm_block(snapshot: AutoLoopSnapshot) -> dict:
    """``status["autopilot"]`` -- the arm chip's whole source.

    Exactly one key, carrying a literal ``bool``. ``cockpit/arm.py``
    resolves it with an ``is`` identity check in both directions, so a
    truthy non-bool (``1``, a numpy scalar, a mock) renders ``ARM ?``
    rather than a confident wrong state. ``bool()`` here means the chip
    can always reach a definite answer, and that the answer is the one
    :func:`observe` computed."""
    return {"running": bool(snapshot.running)}


def intervention_block(snapshot: AutoLoopSnapshot) -> Optional[dict]:
    """``status["intervention"]`` -- the cockpit STOP banner's source
    (``cockpit/stopbanner.py`` defines this wire shape), or ``None`` when
    there is no halt to show.

    ``None`` (the key omitted entirely) rather than
    ``{"needs_attention": False}`` for a daemon that has never run a
    loop: absence is what the banner already treats as "no halt", and an
    omitted key keeps every existing status consumer byte-identical to
    before this module existed.

    A halt raises the banner and keeps it raised until the next ``start``
    replaces the report. That is the honest duration: the run halted, the
    keyboard is the human's, and nothing has happened since to change
    either. The reason code travels unmodified and unlabelled -- the
    banner's resolver is open by construction and renders an unknown code
    as its own text, so a new halt cause reaches the operator on the day
    it ships rather than the day someone writes it a label."""
    report = snapshot.report
    if report is None or not report.halted:
        return None
    reasons = [{"code": report.reason}] if report.reason else []
    return {"needs_attention": True, "reasons": reasons}


def run_wire(snapshot: AutoLoopSnapshot) -> dict:
    """The ``autoloop_status`` verb's body: the run report, or an honest
    absence.

    ``run: null`` distinguishes "this daemon has never been asked to play
    anything" from "a run finished"; a consumer doing ``resp["run"]
    ["outcome"]`` fails loudly on the former rather than reading a
    fabricated idle record."""
    report = snapshot.report
    if report is None:
        return {"running": bool(snapshot.running), "run": None}
    return {
        "running": bool(snapshot.running),
        "run": {
            "loop": report.loop,
            "outcome": report.outcome,
            "reason": report.reason,
            "halted_at": report.halted_at,
            "sends_issued": report.sends_issued,
            "error": report.error,
            "stop_requested": report.stop_requested,
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            # An int or `null`, never omitted: `null` here is the positive
            # statement "this run had no stop-loss", which an operator needs
            # to be able to read as clearly as they read a number.
            "floor": report.floor,
        },
    }


def observe(runner, control_lock) -> AutoLoopSnapshot:
    """The ONE way a surface learns the arm state.

    With a runner, the answer is its own atomic snapshot. Without one (a
    bare unit-test harness, or a daemon built before this module), the
    answer still consults the control lock rather than defaulting to
    ``False``: "nothing here can run a loop" is not the same claim as
    "the App does not hold the connection", and only the second is what
    the arm chip renders. A daemon that somehow held the exclusive hold
    with no runner behind it would report ``ARM ON`` -- which is the true
    and useful answer, not the flattering one."""
    if runner is not None:
        return runner.snapshot()
    return AutoLoopSnapshot(running=_lock_held(control_lock))


# ---------------------------------------------------------------------------
# The port -- I/O only, no decisions
# ---------------------------------------------------------------------------


class _ReplayPort:
    """``loops.player.ReplaySession`` over the daemon's real ``Session``.

    Deliberately dumb. X3's split of labour is that "the port does I/O and
    [the player] does all of the deciding ... Everything a wrong answer
    could make unsafe lives there, under test, rather than in an adapter
    that ships untested next to a real socket." So there is no refusal
    here that the player does not already make: no re-check of the lock
    inside :meth:`send_and_confirm`, no screen classification, no anchor
    comparison. A second copy of a guard here would also make the player's
    own guard tests pass for the wrong reason.

    Every method answers a literal ``bool`` where the player demands one.
    Both underlying settle calls return TUPLES whose every value is truthy
    (``("timeout", 8.0)``, ``("prompt", 0.4, False)``), and forwarding one
    is the single most dangerous mistake an adapter can make: it would
    read a timed-out settle as settled, or make every send read as
    confirmed -- a blind pump straight through a taught macro.
    """

    def __init__(
        self,
        session,
        control_lock,
        stop_event: threading.Event,
        *,
        timeout_s: float = SETTLE_TIMEOUT_S,
        debounce_ms: int = SETTLE_DEBOUNCE_MS,
    ) -> None:
        self._session = session
        self._control_lock = control_lock
        self._stop = stop_event
        self._timeout_s = timeout_s
        self._debounce_ms = debounce_ms

    def settle(self) -> bool:
        """``wait_until_settled`` -- the pre-send freshness gate, which is
        the one that can confirm a screen that was ALREADY quiet when we
        arrived (``wait_for_settle`` structurally cannot: it needs new
        bytes during its own window). Boundary 0 is exactly that case:
        the daemon has been sitting at a prompt since before the run
        started."""
        reason, _elapsed = _settle.wait_until_settled(
            self._session,
            debounce_ms=self._debounce_ms,
            timeout_s=self._timeout_s,
        )
        return reason == "idle"

    def screen(self) -> tuple[str, str]:
        """``(full text, prompt line)`` from ONE ``render()``.

        One render, threaded into ``render_text()``, because two calls are
        two lock acquisitions with a byte able to land between them -- the
        race ``Session.render_with_color()`` documents. Here it would be
        worse than a mismatched colour map: the classification and the
        sector read would describe two different screens, and the sector
        is what the start-anchor guard compares.

        This is also the run's CREDITS capture point, and it has to be:
        a background replay renders and classifies every screen without
        ever passing through ``protocol.build_response()``, so a run driven
        from here would leave the sticky balance frozen at whatever the last
        human ``do`` saw -- ageing quietly past the staleness window while
        the macro spent. (That is not hypothetical; the archive shipped
        exactly that gap and had to move the capture out of ``protocol.py``
        for the same reason.) Capturing off the SAME render the boundary
        was decided on is what makes "the balance behind this decision" and
        "the screen behind this decision" the same instant.

        Unconditional, not gated on whether this run has a floor: the
        capture is a cheap parse with no decision attached, and a sticky
        balance that only updates on floored runs would be a different
        surface depending on how the last run was armed."""
        rows = self._session.render()
        text = self._session.render_text(rows)
        observe = getattr(self._session, "observe_credits", None)
        if callable(observe):
            # `getattr`-guarded exactly like `_lock_held`, for the bare test
            # harnesses that predate this method. Fail-closed either way: a
            # session that cannot observe leaves the balance `absent`, and
            # `absent` is a HALT on any floored run -- never a shrug.
            observe(text)
        return text, (rows[-1].strip() if rows else "")

    def credits(self) -> object:
        """The session's own sticky balance, forwarded WHOLE.

        No unpacking, no ``(balance, ts)`` pair, no age computed here: the
        snapshot is already the validated type the player's floor check
        demands, and every tuple shape is truthy, so an adapter that
        "helpfully" flattened this would hand a truthiness test a healthy-
        looking answer for a balance nobody ever observed.

        Reached only on a floored run -- ``replay_loop`` does not call it
        otherwise -- and ``AutoLoopRunner.start`` has already refused to arm
        a floor against a session that cannot answer, so the attribute is
        present by the time this runs. Deliberately UNguarded for that
        reason: a ``getattr`` default here would invent an answer at the one
        call site whose whole job is to report a real one."""
        return self._session.credits_snapshot()

    def send_and_confirm(self, keystrokes: str, wait_prompt: Optional[str]) -> bool:
        """THE wire call. Returns the third element of the settle layer's
        3-tuple, as a literal ``bool``.

        ``enter=True`` because canon's macro schema records no per-step
        enter field and the archived replay sent one for every step
        (X3's own note): choosing ``False`` here would silently change
        what every taught macro means.

        ``match_scope=MATCH_SCOPE_PROMPT_LINE`` is DECISIONS §D applied to
        a drive send -- settle-detection's prompt-line discipline is the
        default for verbs that send, and a replay step sends. TradeWars
        is a scrolling BBS door, so a recorded ``Command [TL=`` target is
        routinely still visible up the grid from two screens ago; a
        whole-screen search would confirm this step against that stale
        row. The cost is stated where it lands: a recorded ``wait_prompt``
        that only ever matched a BODY line can no longer be confirmed, so
        that step times out and the run halts ``confirm_failed``. A missed
        confirm, never a wrong one."""
        _reason, _elapsed, confirmed = _settle.send_and_confirm(
            self._session,
            keystrokes,
            confirm_prompt=wait_prompt,
            enter=True,
            timeout_s=self._timeout_s,
            debounce_ms=self._debounce_ms,
            match_scope=MATCH_SCOPE_PROMPT_LINE,
        )
        return confirmed is True

    def is_driver_fenced(self) -> bool:
        """Is the exclusive App hold this run took still ours?

        Deliberately NOT ``control_lock.is_driver_fenced()`` -- see the
        module docstring's "The fence wiring, a trap in it, and the
        trap's later repair". ``take_human()`` clears the hold
        unconditionally, so this is what actually catches a human
        attaching mid-run, and it catches it at the next boundary, before
        the next send.

        Reads ``is_auto_loop_held()`` -- *"is some hold currently
        standing"*, not *"is MY generation's hold still standing"*; it
        takes no generation argument and cannot distinguish the two. That
        is only safe because ``AutoLoopRunner`` never lets a second
        generation's thread exist while this one is alive (see the module
        docstring's retraction of this method's earlier "defense in
        depth" framing) -- recorded for ``WO-WEDGED-SEND-FENCE-STICKS``,
        not fixed here."""
        return not _lock_held(self._control_lock)

    def should_abort(self) -> bool:
        """Has this run been stood down? The ``autoloop_stop`` verb's
        whole mechanism -- it sets this event and nothing else, and the
        player turns it into an ``operator_stop`` halt at the next
        boundary."""
        return self._stop.is_set()


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------


class AutoLoopRunner:
    """Owns the background thread, the exclusive hold, and the last run's
    report. One instance per daemon; ``daemon.main()`` builds it.

    Lock order is ``_mutex`` -> ``ControlLock``, always, and nothing in
    the other direction: ``ControlLock`` knows nothing about this class,
    so ``take_human()`` can preempt a run from an attach thread while this
    mutex is held elsewhere.

    ``stop()`` joins OUTSIDE the mutex, deliberately -- the thread it is
    waiting for needs that same mutex to finish, and joining under it
    would deadlock the daemon on its own stop verb.
    """

    def __init__(
        self,
        session,
        control_lock,
        *,
        state_dir=None,
        timeout_s: float = SETTLE_TIMEOUT_S,
        debounce_ms: int = SETTLE_DEBOUNCE_MS,
        log_error=None,
    ) -> None:
        self._session = session
        self._control_lock = control_lock
        self._state_dir = state_dir
        self._timeout_s = timeout_s
        self._debounce_ms = debounce_ms
        self._log_error = log_error
        self._mutex = threading.Lock()
        self._in_flight = False
        self._thread: Optional[threading.Thread] = None
        self._stop: Optional[threading.Event] = None
        self._report: Optional[RunReport] = None

    # -- reads ----------------------------------------------------------

    def snapshot(self) -> AutoLoopSnapshot:
        """Arm state and last report, captured under one mutex hold.

        ``in_flight or <hold>`` is the arm-honesty rule in one expression;
        see the module docstring for why neither forbidden state is
        reachable through it. The lock is asked from INSIDE the mutex so
        that a run's end-of-life transition (which takes the same mutex)
        cannot land between the two reads."""
        with self._mutex:
            running = bool(self._in_flight or _lock_held(self._control_lock))
            return AutoLoopSnapshot(running=running, report=self._report)

    # -- writes ---------------------------------------------------------

    def start(self, name: str, floor: Optional[int] = None) -> AutoLoopSnapshot:
        """Arm and run ONE pass of the macro called ``name``, optionally
        under a credit floor.

        Returns as soon as the thread is running (canon: "``start``
        returns immediately"). Raises :class:`AutoLoopRefused` -- having
        touched neither the control lock nor the session -- when the macro
        cannot be loaded, and the load happens FIRST for that reason: the
        arm-confirm rail is "preconditions unconfirmed ⇒ instant-die,
        never arm blind", and a name that resolves to nothing is an
        unconfirmed precondition. Nothing is ever armed for a run that
        cannot start.

        **A floor this daemon cannot enforce is refused here**
        (``floor_unsupported``), before the lock is entered and before a
        thread exists. That refusal is the point of the whole slice: an
        unenforceable floor accepted at this layer would render on the run
        report as a live stop-loss, and the operator would be reading a
        safety claim nothing behind it can make. It is checked against the
        SESSION's ability to observe credits rather than against a config
        flag, so it cannot be satisfied by asserting it.

        Note what is NOT checked here: whether a balance has actually been
        observed yet. That is boundary 0's job inside the run, and it
        belongs there because boundary 0 settles and renders first -- so it
        decides on a reading taken after the run began, not on whatever was
        sticky when the operator typed the verb. A run armed with a floor
        and no balance in hand halts ``credits_unknown`` at boundary 0
        having sent nothing, which is canon's instant-die with a typed
        reason attached rather than a bare refusal.

        Drafts are not consulted (``include_drafts`` is left at its
        default and is not exposed on the wire): a draft is an inert
        proposal awaiting human approval, and approval is expressed by
        file location. A background driver playing an unapproved macro
        would be the human-approval gate failing open.

        **Asserts "at most one auto_loop generation outstanding" as a
        loud, typed failure** (:class:`AutoLoopInvariantViolation`, not
        :class:`AutoLoopRefused`) rather than leaving it merely true by
        construction. ``ControlLock`` itself permits any number of
        outstanding generations -- that permissiveness is what its own
        fence fix depends on -- so the bound this runner relies on
        (``_in_flight`` refuses a second ``start()`` before an earlier
        run's own release) is THIS class's discipline, not the lock's.
        Nothing pins that discipline anywhere else; a future second call
        site to ``enter_auto_loop()``, or a loosened one-runner-per-daemon
        rule, would find the lock fully willing to accommodate it in
        silence. Checked here, immediately before granting, so that day
        produces a crash with a traceback instead of two drivers quietly
        sharing the one wire.
        """
        if floor is not None:
            # `True` is an int and would arm a floor of 1 -- the same trap
            # every other numeric field in this tree documents on its own
            # half. A float is refused rather than coerced: a credit balance
            # is a whole number, and silently rounding a caller's floor is
            # how the enforced number stops being the requested one.
            if isinstance(floor, bool) or not isinstance(floor, int):
                raise AutoLoopRefused("invalid_floor")
            if floor < 0:
                # A negative floor can never be crossed, so it is a stop-loss
                # that structurally cannot stop -- the decorative flag this
                # slice exists to forbid, wearing a number.
                raise AutoLoopRefused("invalid_floor")
            if not _can_observe_credits(self._session):
                raise AutoLoopRefused("floor_unsupported")
        loop = self._load(name)
        stop = threading.Event()
        report = RunReport(loop=loop.name, started_at=_utc_now(), floor=floor)
        with self._mutex:
            if self._in_flight:
                # The lock would refuse a second enter too, but refusing
                # here keeps `enter_auto_loop` un-called on this path --
                # a second acquisition attempt is not a thing to lean on.
                raise AutoLoopRefused("already_running")
            # WO-CONTROL-LOCK-AUTOLOOP-FENCE (Mack's LOW, round 5): the
            # lock's OWN contract permits any number of outstanding
            # generations (see its module docstring) -- the "at most one"
            # bound is this class's discipline, not the lock's, and lives
            # ONLY in the `_in_flight` check just above. Pin that external
            # invariant explicitly rather than let it stay merely true by
            # construction: if a future change ever reaches this point
            # with the lock already carrying an unreleased generation --
            # a second call site, a loosened one-runner-per-daemon rule --
            # fail LOUD here instead of quietly minting a second
            # concurrent generation on top of it. Deliberately NOT a bare
            # `assert` (`-O` strips those) and deliberately NOT an
            # `AutoLoopRefused` (that reads on the wire as an ordinary,
            # expected no-thanks; this is a bug report).
            outstanding = self._control_lock.outstanding_auto_loop_generations()
            if outstanding:
                raise AutoLoopInvariantViolation(
                    "at most one auto_loop generation may ever be outstanding, "
                    f"but the lock already carries {sorted(outstanding)!r} while "
                    "`_in_flight` was False"
                )
            try:
                generation = self._control_lock.enter_auto_loop()
            except ControlModeConflict as exc:
                # The lock's own closed vocabulary: locked_by_human_attach
                # / already_running / locked_by_active_driver. Not
                # re-spelled -- a second dialect for a refusal is how two
                # surfaces start disagreeing about the same event.
                raise AutoLoopRefused(str(exc)) from None
            # WO-CONTROL-LOCK-AUTOLOOP-FENCE (Mack's CRITICAL): the thread
            # is built HERE, after the grant, so it can close over the
            # generation token THIS hold actually received -- never a
            # shared/instance-level value a later run could stomp on, and
            # never guessed. `_run`'s own `finally` hands this exact value
            # back to `leave_auto_loop()`, so a stale release can never
            # touch a hold this run does not own.
            thread = threading.Thread(
                target=self._run,
                args=(loop, stop, report, generation),
                name="tw-autoloop",
                daemon=True,
            )
            self._in_flight = True
            self._stop = stop
            self._thread = thread
            self._report = report
            try:
                thread.start()
            except Exception as exc:
                # Armed but with nothing behind it: exactly the state the
                # chip must never show. Unwind it here rather than leave a
                # thread-less hold for `stop` to discover. Same token this
                # grant received -- nothing else could be correct here,
                # since no OTHER generation exists yet.
                self._control_lock.leave_auto_loop(generation)
                self._in_flight = False
                self._thread = None
                self._stop = None
                self._report = replace(
                    report,
                    outcome=OUTCOME_CRASHED,
                    reason=REASON_PLAYER_ERROR,
                    error=type(exc).__name__,
                    finished_at=_utc_now(),
                )
                raise AutoLoopRefused("thread_start_failed") from None
        # Read AFTER the mutex, deliberately: a one-pass run can finish
        # before this returns, and answering with a hardcoded
        # `running=True` would describe an instant that has already
        # passed. `snapshot()` reports the state the caller is actually
        # returning to -- including, honestly, a run that is already over.
        return self.snapshot()

    def stop(self, join_timeout: float = STOP_JOIN_TIMEOUT_S) -> AutoLoopSnapshot:
        """Stand the run down. Idempotent, and safe with nothing running.

        Sets the player's arm predicate and waits (bounded) for the run to
        die. It does NOT call ``leave_auto_loop()``: the run owns its own
        hold from ``enter`` to ``finally``, and a second release path
        would drop the App's exclusivity while a step was still in flight
        -- letting a concurrent ``do`` interleave on the one wire.

        The answer is taken AFTER the join, so a stop that worked reports
        ``running: false`` and a stop that ran out of patience reports
        ``running: true``. Neither is a promise about the other."""
        with self._mutex:
            stop = self._stop
            thread = self._thread
        if stop is not None:
            stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(join_timeout)
        return self.snapshot()

    # -- internals ------------------------------------------------------

    def _load(self, name: str):
        """Resolve ``name`` to a validated macro, or refuse with a typed
        code that keeps the loader's four outcomes apart.

        "Not found" and "could not finish looking" are different facts and
        are never collapsed -- that collapse is the defect this repo has
        fixed four times. The name is echoed (the caller supplied it); the
        loader's PATHS and per-step defects are not, because those are
        server-side layout the client never had."""
        try:
            return load_loop(name, state_dir=self._state_dir)
        except LoopNotFound:
            raise AutoLoopRefused(f"loop_not_found:{name}") from None
        except LoopUnreadable:
            raise AutoLoopRefused(f"loop_unreadable:{name}") from None
        except LoopMalformed:
            raise AutoLoopRefused(f"loop_malformed:{name}") from None
        except LoopAmbiguous:
            raise AutoLoopRefused(f"loop_ambiguous:{name}") from None

    def _run(self, loop, stop: threading.Event, report: RunReport, generation: int) -> None:
        """The thread body: one pass, then die.

        There is no ``for`` and no ``while`` around the ``replay_loop``
        call, and that absence is the whole of "no repetition" -- see the
        module docstring. A halt is not retried: the player's answer is
        recorded and the run ends, because a driver that re-invoked after
        a halt would be pressing into a screen the guard just refused.

        ``generation`` is the exact token ``start()`` received from
        ``enter_auto_loop()`` for THIS run -- threaded through as a plain
        argument (not read off ``self`` at release time) so a wedged run
        that outlives a human detach-and-re-arm cycle still releases only
        the hold it actually took, never whatever a later ``start()`` put
        in its place (WO-CONTROL-LOCK-AUTOLOOP-FENCE, Mack's CRITICAL).
        """
        port = _ReplayPort(
            self._session,
            self._control_lock,
            stop,
            timeout_s=self._timeout_s,
            debounce_ms=self._debounce_ms,
        )
        outcome = OUTCOME_CRASHED
        reason: Optional[str] = REASON_PLAYER_ERROR
        halted_at: Optional[int] = None
        sends: Optional[int] = None
        error: Optional[str] = None
        try:
            # `report.floor` rather than a second stored field: the report
            # IS this run's record of what it was armed with, so the number
            # the player enforces and the number the operator reads cannot
            # be two different values.
            result = replay_loop(loop, port, floor=report.floor)
        except Exception as exc:  # noqa: BLE001 -- an adapter fault must still release
            # TYPE NAME only on anything a client can read; the text and
            # frame chain go to the daemon's owner-only local log
            # (`daemon._log_dispatch_error`'s split, same reasoning).
            error = type(exc).__name__
            self._record_error(exc)
        else:
            outcome = result.outcome
            reason = result.reason
            halted_at = result.halted_at
            # The player's own count -- never defaulted. `0` would be an
            # affirmative zero-bytes claim, which only the player may make.
            sends = result.sends_issued
        finally:
            finished = replace(
                report,
                outcome=outcome,
                reason=reason,
                halted_at=halted_at,
                sends_issued=sends,
                error=error,
                stop_requested=stop.is_set(),
                finished_at=_utc_now(),
            )
            with self._mutex:
                # Release BEFORE the flags are cleared, inside one mutex
                # hold, so no observer can see a released lock with
                # `in_flight` still set, or a held lock with it clear.
                # `leave_auto_loop` never clobbers a mode someone else set
                # -- if `take_human()` already took the hold away, MODE
                # stays theirs and the human keeps the keyboard. It is NOT
                # a pure no-op in that case, though (WO-CONTROL-LOCK-
                # AUTOLOOP-FENCE): `take_human()` fenced the preemption
                # (`is_driver_fenced()` -> True), and THIS call is what
                # clears that fence -- the run's own wind-down actually
                # completing is what lets `Session.send_raw`'s bounded
                # wait on a human's attach keystroke stop waiting early
                # instead of sitting out the full bound. `generation` is
                # THIS run's own token (a plain argument, not read off
                # `self`) -- Mack's CRITICAL: a stale release must only
                # ever be able to touch the hold it actually took, never
                # whatever a later `start()` put in its place.
                self._control_lock.leave_auto_loop(generation)
                self._report = finished
                self._in_flight = False
                self._thread = None
                self._stop = None

    def _record_error(self, exc: BaseException) -> None:
        """Hand the traceback to the daemon's local sink, if one was
        wired. A broken diagnostic must never be the thing that kills the
        run's release path, so this cannot raise."""
        if self._log_error is None:
            return
        try:
            self._log_error(exc)
        except Exception:  # noqa: BLE001 -- diagnostics never take the daemon down
            pass
