"""Replay ONE taught macro -- the module that actually presses keys.

WO-P2-G4-X3. Everything else in this package reads: ``store`` lists what
is on disk, ``loader`` validates one document for execution. This is the
first module in ``loops/`` that can put a keystroke on the wire, and every
decision below is shaped by that.

It presses back only what a human already demonstrated. It never chooses a
keystroke, never composes one, never retries, never substitutes a "probably
equivalent" key, and never presses on past a screen it cannot positively
identify. A replay is a recording being played, not a plan being executed
(``canon/architecture/north-star.md``: the App "plays back only the screens
it has been taught... The instant the app meets a screen it does not
recognize, it stops and hands the keyboard back to the human. It never
guesses.").

Canon
-----
* ``canon/engine/macros.md`` §"Deterministic replay" is the step contract:
  send-and-confirm each keystroke; treat an unconfirmed send as a surprise
  and halt *without* classifying the screen it already knows is
  untrustworthy; re-classify a confirmed settle and compare it to the
  step's ``expected_post_class``; halt on any divergence carrying the trace
  up to and including the failing step.
* ``canon/engine/macros.md`` §"Start-anchor -- refuse on context mismatch"
  is the pre-flight: before the first send of *every* replay invocation,
  read the current sector and validate it against ``start_anchor``. A
  present anchor that differs "(or can't be read at all)" halts and is
  **not** bypassable by force -- "forcing past a *detected* mismatch is the
  danger itself". A *null* anchor (a legacy macro) refuses by default and
  is the one case an explicit force may waive.
* ``canon/architecture/app-autopilot-model.md`` §"Re-Validate Every Cycle"
  is why the gate below runs at every boundary rather than only at entry:
  "Mid-run STOP and entry-time STOP are the same mechanism, deliberately:
  there is no 'we're already committed, push through' state."
* ``canon/doctrine/action-safety-guards.md`` §"Structural rails" names the
  novelty-halt rail this module implements ("Every cycle re-validates the
  screen match; the first unrecognized frame halts the loop") and the
  fail-closed direction every guard here takes.
* ``canon/DECISIONS.md`` §A.2 (Accepted 2026-07-26) is the money-path
  ruling -- see "The never-auto refusal" below.
* ``canon/architecture/control-and-escalation.md`` §"Escalation reason-code
  catalog" owns the reason vocabulary. The catalog is "open by
  construction" -- an unknown code renders as its own raw text -- so the
  codes below that canon does not yet name are additions, not inventions
  in a closed namespace. Family attribution is stated per code.
* ``canon/research/archive-port-patterns.md`` AP-04 is the archived
  ``skills.replay_skill`` this module re-roots. Its reason spellings
  (``start_anchor_mismatch``, ``confirm_failed``, ``post_class``) are
  carried VERBATIM rather than re-spelled: two of the three are canon's own
  words, and a third dialect for the same three ideas is exactly the drift
  this repo keeps paying for.

Zero bytes is the property, not the halt reason
-----------------------------------------------
Every refusal below is proven by a session whose ``send_and_confirm``
RAISES, not by inspecting the reason a halt reported. A player that sent
first and reported the refusal afterwards would satisfy every
reason-checking test ever written and would still have pressed a key into
a screen it did not recognize. So the shape of this module is: **observe,
gate, and only then send** -- there is exactly one call site that reaches
the wire, it is inside the step loop, and it is unreachable until a full
observe-and-gate has passed.

Boundaries, not phases
----------------------
The run is a sequence of BOUNDARIES with sends between them:

    boundary 0 -> send step 0 -> boundary 1 -> send step 1 -> ... -> boundary N

Each boundary is settled once, read once, classified once, and gated once.
Boundary ``i+1`` is simultaneously step ``i``'s post-send check and step
``i+1``'s pre-send check -- they are the same screen, and observing it
twice would both double the settle cost and invent a window in which two
readings of one screen could disagree. Canon asks that "every send is
preceded by a fresh render and a re-classification of the current screen"
(``app-autopilot-model.md`` §"Chain Execution"); a boundary satisfies that
because no send occurs between the observation and the send it gates.

Boundary 0 additionally carries the start-anchor check, because canon
scopes that to "before the first send of *every* replay invocation".

What a step does NOT constrain: its own pre-screen. A macro's schema
(``macros.md`` §Schema) records ``expected_post_class`` and no
``expected_pre_class``, so for steps 1..N the previous step's post-class IS
the pre-condition (same boundary, already compared), and for step 0 there
is nothing recorded at all. Step 0's pre-send screen is therefore guarded
by the start-anchor plus the gate below, and by nothing else -- stated
because it is a real gap in the recorded schema, not an omission here.

The three anchor outcomes, held apart
-------------------------------------
``state_parser.read_current_sector`` (X1) answers ``read`` / ``absent`` /
``unreadable``, and a macro's ``start_anchor`` is an int or ``None``. That
is four facts, and collapsing any pair of them is how a replay runs from
the wrong sector:

===========================  ===============================  ===========
recorded anchor              current-sector read              outcome
===========================  ===============================  ===========
``None`` (legacy macro)      not consulted                    refuse, ``start_anchor_missing`` -- **the one forceable halt**
int                          ``read``, equal                  **compare passes** -- the only path to a send
int                          ``read``, different              halt, ``start_anchor_mismatch`` -- force does NOT bypass
int                          ``absent``                       halt, ``current_sector_absent`` -- force does NOT bypass
int                          ``unreadable``                   halt, ``current_sector_unreadable`` -- force does NOT bypass
===========================  ===============================  ===========

The trap is that ``start_anchor is None`` and ``outcome == "absent"`` both
read as "there is nothing here", and canon gives exactly one of them a
force path. A null anchor means *the recording never captured a
precondition*, so there is nothing to disagree with; an absent current read
means *the recording has a precondition and reality declined to state
whether it holds*, which is canon's "can't be read at all" -- a live
surprise, and the danger itself to force past. ``absent`` and
``unreadable`` share the halt but keep separate codes because X1's entire
thesis is that they are different facts for the operator: ``absent`` on a
``main_command`` screen is the documented CLASSIC-shape prompt that carries
no sector bracket at all, while ``unreadable`` is a damaged bracket -- a
poll that landed mid-paint. Same decision, different repair.

Settle before you look
----------------------
X1's docstring is explicit that settling is the caller's job: ``state`` is
the cheap poll and does not settle, and a poll landing mid-paint is exactly
what its ``damaged_command_prompt`` outcome exists to surface. This module
is that caller. Every boundary settles through the port FIRST and reads
only after; a port that cannot settle produces ``settle_failed`` and no
send. A mid-paint read would at best yield ``unreadable`` (a halt) and at
worst a plausible-wrong sector that satisfies the anchor check -- which is
the live incident ``macros.md`` was written to prevent.

The never-auto refusal (§A.2)
-----------------------------
``classify.NEVER_AUTO_ACTION_CLASSES`` is refused at every boundary,
BEFORE the send that boundary gates. The set is imported, never restated,
because ``classify.py``'s own comment makes that the condition of the pin
holding: "it only holds while consumers derive their refusals from this
name rather than restating it... anything that later decides whether a
rule may fire owes the same." This module is that "anything".

§A.2 exempts a "human-armed autopilot with an explicit taught/guarded
rule". **This module cannot be that exemption, and does not claim it.** A
``Loop`` from the loader carries no guard field and no arming field -- the
schema has neither -- and the arm gate is canonically "a required, external
input to the loop, not an internal self-check the loop could grant itself"
(``app-autopilot-model.md`` §"Arm-Confirm"). A replay driven from here is
therefore unattended-and-unguarded by construction, which is precisely the
half §A.2 says still refuses. There is deliberately no flag to switch that
off: a flag would BE the self-granted arming canon forbids.

The consequence is real and is not a bug: a taught trade macro whose steps
answer "How many holds of Fuel Ore do you want to buy?" halts at that
boundary under this player. Unblocking it needs the arming and guard
substrate that does not exist yet, not a bypass here.

Halting is normal, so it is returned, not raised
------------------------------------------------
Canon: "halting is the *normal, correct* outcome whenever reality no longer
matches -- not an error to suppress." The archived engine raised
(``ReplayDivergence``); this returns a frozen :class:`ReplayResult`. Both
shapes have a failure mode -- an exception can be swallowed by a bare
``except``, a return value can be ignored -- and the deciding argument is
that ignoring this one cannot become a blind pump: the gate is re-run from
scratch at boundary 0 of the NEXT invocation, so a caller that ignored a
halt and replayed again gets the same refusal before any byte, not a
resumption. (What it does not prevent is a caller re-pressing step 0 after
a mid-run halt while still standing in the anchor sector. Bounding
re-arming after an escalation is the run-loop's job -- see "What this slice
is not".)

:class:`ReplayResult` has no ``__bool__``, no ``ok``, and no truthiness
shortcut, for the reason ``SectorRead`` gives for the same omission: a
caller must pass through the outcome to learn anything, and there is no
expression that quietly folds "halted" into "fine".

What this slice is NOT
----------------------
There is no cycle count and no repetition here, and that is a boundary,
not an omission. ``scope: repeating`` is driven by the run-loop, which owns
the rails that make repetition safe -- turn-budget clamp, stop-loss floor,
hazard-halt, arm-confirm (``action-safety-guards.md`` §"Structural rails",
``app-autopilot-model.md`` §"Background AUTO-LOOP Posture"). A ``cycles=N``
parameter here would ship the repetition without any of them, which is the
dangerous half on its own. A caller that wants N cycles calls this N times
and gets canon's per-cycle start-anchor re-check for free, exactly as the
archived ``play_skill`` got it from ``replay_skill``.

Also absent, deliberately: no ledger rows (``macros.md`` §"Ledgering a
replay" -- ``actor=trainer``), no parameter substitution (``_apply_params``
in the archive), no ``autoloop`` CLI verb, no daemon driver, no wire
serializer. Each belongs to a slice that owns its own surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from ..session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from ..session.state_parser import (
    OUTCOME_ABSENT,
    OUTCOME_READ,
    OUTCOME_UNREADABLE,
    SectorRead,
    read_current_sector,
)
from .loader import Loop, LoopStep

__all__ = [
    "FORCEABLE_HALTS",
    "HALT_CONFIRM_FAILED",
    "HALT_CURRENT_SECTOR_ABSENT",
    "HALT_CURRENT_SECTOR_UNREADABLE",
    "HALT_FENCED",
    "HALT_NEVER_AUTO_ACTION",
    "HALT_POST_CLASS",
    "HALT_REASONS",
    "HALT_SCREEN_UNREADABLE",
    "HALT_SETTLE_FAILED",
    "HALT_START_ANCHOR_MISMATCH",
    "HALT_START_ANCHOR_MISSING",
    "HALT_UNRECOGNIZED_SCREEN",
    "OUTCOME_COMPLETED",
    "OUTCOME_HALTED",
    "OUTCOMES",
    "ReplayResult",
    "ReplaySession",
    "StepTrace",
    "replay_loop",
]


# ---------------------------------------------------------------------------
# The reason vocabulary
# ---------------------------------------------------------------------------
#
# Closed, and every member is attributed to one of canon's STOP-cause
# families (`control-and-escalation.md`). Two spellings are canon's own
# words and one more is the archive's; the rest are new codes the catalog
# admits by being "open by construction".

# desync -- the port could not reach a settled screen inside its budget, so
# there is nothing safe to read, let alone press into.
HALT_SETTLE_FAILED = "settle_failed"
# desync -- the port settled but did not hand back a readable screen. An
# adapter fault rather than a game state, kept distinct from every game
# surprise for the same reason X1 keeps `not_text` distinct from `absent`:
# "could not read" and "read, and it says nothing" want different repairs.
HALT_SCREEN_UNREADABLE = "screen_unreadable"
# human-sovereignty preemption. Canon's catalog names this code verbatim,
# so it is the one halt here that already has a rendered label.
HALT_FENCED = "human_attach_blocks_trainer"
# guard-STOP -- `classify.NEVER_AUTO_ACTION_CLASSES` (DECISIONS §A.2).
HALT_NEVER_AUTO_ACTION = "never_auto_action"
# novelty-halt -- classify could not name the screen. Canon's central
# invariant as a rail: "the first unrecognized frame halts the loop".
HALT_UNRECOGNIZED_SCREEN = "unrecognized_screen"
# guard-STOP -- the recording carries no anchor. THE ONLY FORCEABLE HALT.
HALT_START_ANCHOR_MISSING = "start_anchor_missing"
# guard-STOP -- canon's and the archive's own spelling, unchanged.
HALT_START_ANCHOR_MISMATCH = "start_anchor_mismatch"
# guard-STOP -- an anchor to check, and a screen that makes no claim.
HALT_CURRENT_SECTOR_ABSENT = "current_sector_absent"
# guard-STOP -- an anchor to check, and a claim we could not resolve.
HALT_CURRENT_SECTOR_UNREADABLE = "current_sector_unreadable"
# desync -- canon's and the archive's spelling: the send was never
# positively confirmed (`macros.md` §"Send-and-confirm").
HALT_CONFIRM_FAILED = "confirm_failed"
# guard-STOP -- the archive's spelling for an ordinary post-step
# classification divergence (AP-04: `ReplayDivergence.reason == "post_class"`).
HALT_POST_CLASS = "post_class"

HALT_REASONS = frozenset({
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
})

# The whole content of `force`, as data rather than as scattered branches.
#
# Canon permits force to waive exactly one thing: a macro recorded before
# anchor tracking existed, where "there is nothing to check against". Every
# other halt above is a DETECTED disagreement with reality, and canon's
# words for forcing past one of those are "the danger itself". A future
# reader adding a code to this set is making a canon decision, visibly.
FORCEABLE_HALTS = frozenset({HALT_START_ANCHOR_MISSING})

assert FORCEABLE_HALTS <= HALT_REASONS, (
    "FORCEABLE_HALTS names a reason this module can never report: "
    f"{sorted(FORCEABLE_HALTS - HALT_REASONS)}"
)

OUTCOME_COMPLETED = "completed"
OUTCOME_HALTED = "halted"
OUTCOMES = frozenset({OUTCOME_COMPLETED, OUTCOME_HALTED})

# Canon's own marker for a halt that happened before the first send
# (`macros.md`: "a start-anchor divergence, `step_i = -1`"). Distinct from
# step 0, which means one keystroke DID reach the wire.
BEFORE_FIRST_SEND = -1


# ---------------------------------------------------------------------------
# The port -- the only way this module reaches the wire
# ---------------------------------------------------------------------------


class ReplaySession(Protocol):
    """The live session, reduced to the four things a replay needs.

    This module imports no transport, constructs no session, and holds no
    default: an implementation of this protocol arrives as a required
    argument or the replay does not happen. That is what keeps ``loops/``
    unable to reach the game on its own -- a caller with a real socket has
    to hand one in, deliberately, every time.

    The split of labour is deliberate and one-directional: **the port does
    I/O and this module does all of the deciding.** The port never
    classifies, never compares a sector, never decides whether a send is
    allowed. Everything a wrong answer could make unsafe lives here, under
    test, rather than in an adapter that ships untested next to a real
    socket.

    Every method is reached at boundary 0, before any send. A port missing
    one, or answering one wrongly, therefore costs zero bytes: the first
    ``send_and_confirm`` is unreachable until a full observe-and-gate has
    completed, and that observe-and-gate is the same code at boundary 0 as
    at every later boundary.
    """

    def settle(self) -> bool:
        """Block until the stream is quiet enough to read, then report
        whether it actually settled. ``False`` halts the replay.

        Called before every read, because ``read_current_sector`` and
        ``classify_screen`` are both documented as operating on a SETTLED
        screen and neither can tell that it did not get one.

        An adapter over the daemon core implements this with
        ``settle.wait_until_settled`` -- the pre-send freshness gate whose
        docstring describes exactly this caller: "a caller about to READ
        the current render and act on it"."""

    def screen(self) -> tuple[str, str]:
        """``(full rendered text, current prompt line)`` of the screen
        ``settle()`` just established.

        Two values because the two consumers want different scopes and
        canon is emphatic about not confusing them: ``classify_screen``
        checks gate anchors against the prompt line and content anchors
        against the whole grid, and ``read_current_sector`` takes ONLY the
        prompt line so that "no amount of stale or forged body content can
        reach it".

        The prompt line is ``rows[-1].strip()`` -- the same line
        ``Session.current_prompt_line()`` returns."""

    def send_and_confirm(self, keystrokes: str, wait_prompt: Optional[str]) -> bool:
        """Send ``keystrokes`` and require a POSITIVE confirmation of the
        result. ``False`` means desync and halts the replay.

        This is the one method that touches the wire. It maps onto
        ``settle.send_and_confirm``'s third return value (``confirmed``),
        and the adapter owns everything that call needs which a macro's
        schema does not record -- notably ``enter=`` (``macros.md``
        §Schema has no per-step enter field; the archived replay passed
        ``enter=True`` for every step) and the per-step timeout. Recorded
        here because an adapter silently choosing ``enter=False`` would
        change what every taught macro means.

        Answer literally ``True`` or literally ``False``. **Do not forward
        ``settle.send_and_confirm``'s return value** -- it is the 3-tuple
        ``(reason, elapsed, confirmed)``, which is truthy no matter what it
        confirmed; return its third element. Anything that is not ``True``
        is treated as unconfirmed and halts the replay. The same warning
        applies to :meth:`settle` and ``wait_until_settled``'s
        ``(reason, elapsed)``.

        ``wait_prompt`` is the step's recorded confirmation target or
        ``None``. It is passed through unmodified and uncompiled: the
        loader has already proven it compiles under exactly the call the
        settle layer makes, and canon's hard rule is that these regexes are
        case-sensitive -- a mismatched pattern must time out, never be
        "helpfully" widened here or downstream."""

    def is_driver_fenced(self) -> bool:
        """Has a human taken the keyboard? ``True`` halts the replay.

        Checked at every boundary, which is to say before every send, so a
        human's attach lands within one send-step (``app-autopilot-model.md``
        §"Chain Execution": the abort predicate is checked "at the same
        choke-point as every other guard"). Human sovereignty is not a
        thing the App negotiates: the moment the human holds the keyboard,
        the App stops pressing, whatever screen is showing."""


# ---------------------------------------------------------------------------
# What a caller gets back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepTrace:
    """One step that was actually attempted, and what came of it.

    Present for every step whose send was ISSUED -- including the failing
    one, per canon's "carrying the full trace up to and including the
    failing step". A step never reached carries no row, so the trace length
    is the number of sends, never a plan.

    ``observed_class`` is ``None`` when the boundary after this step never
    produced a classification: either the send was not confirmed (canon
    forbids classifying a screen already known to be untrustworthy) or the
    boundary failed to settle or to read.
    """

    index: int
    input: str
    wait_prompt: Optional[str]
    expected_post_class: str
    confirmed: bool
    observed_class: Optional[str]


@dataclass(frozen=True)
class ReplayResult:
    """The outcome of one replay invocation.

    Deliberately has no ``__bool__``, no ``ok``, and no ``or``-friendly
    default -- the same omission, for the same reason, as
    ``state_parser.SectorRead``: there is no expression that folds
    ``halted`` into a passing value at a call site.

    Field pairings are enforced in ``__post_init__`` rather than promised
    in prose: ``reason`` and ``halted_at`` accompany exactly a halt, and
    ``reason`` is drawn from :data:`HALT_REASONS`. A result therefore
    cannot exist that says "completed" while carrying a halt reason, nor
    one that halts for a reason no code path can produce.

    ``anchor_read`` is boundary 0's current-sector verdict -- the X1
    ``SectorRead`` the start-anchor check was made against -- and is
    ``None`` only when the run halted before any read was taken (a port
    that could not settle, or a fence at the very first look). It is
    carried whole rather than flattened to an int so that "absent" and
    "unreadable" stay distinguishable in the answer, exactly as they are
    in the decision.

    Nothing here carries screen text. Every string in a result is either a
    member of a closed vocabulary (``outcome``, ``reason``,
    ``observed_class``) or came off the macro on disk (``input``,
    ``wait_prompt``, ``expected_post_class``) -- so a surface that renders
    a result cannot leak a server-echoed credential into a structured
    answer (``canon/DECISIONS.md`` §C.2 / §C.2.1). Shaping it for a wire
    is a surface's job and is not done here.
    """

    outcome: str
    loop_name: str
    steps: tuple[StepTrace, ...]
    sends_issued: int
    reason: Optional[str] = None
    halted_at: Optional[int] = None
    anchor_read: Optional[SectorRead] = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome {self.outcome!r} is not one of {sorted(OUTCOMES)}")
        halted = self.outcome == OUTCOME_HALTED
        if halted != (self.reason is not None):
            raise ValueError(
                "a reason accompanies exactly the 'halted' outcome -- "
                f"got outcome={self.outcome!r} with reason={self.reason!r}"
            )
        if halted != (self.halted_at is not None):
            raise ValueError(
                "a halted_at index accompanies exactly the 'halted' outcome -- "
                f"got outcome={self.outcome!r} with halted_at={self.halted_at!r}"
            )
        if self.reason is not None and self.reason not in HALT_REASONS:
            raise ValueError(f"reason {self.reason!r} is not one of {sorted(HALT_REASONS)}")


# ---------------------------------------------------------------------------
# Observing a boundary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Observation:
    """One settled boundary, as seen through the port.

    ``failure`` is set when the boundary could not be established at all,
    in which case ``klass`` and ``sector`` are ``None`` and nothing
    downstream may read them.
    """

    klass: Optional[str] = None
    sector: Optional[SectorRead] = None
    fenced: bool = False
    failure: Optional[str] = None


def _is_screen(value) -> bool:
    """A ``(str, str)`` pair, checked rather than trusted.

    An adapter handing back bytes, ``None``, or a bare string would
    otherwise reach ``classify_screen`` and raise from inside the guard
    layer -- an untraced crash on the one surface whose whole job is to
    produce a traced, typed refusal.
    """
    return (
        isinstance(value, (tuple, list))
        and len(value) == 2
        and all(isinstance(part, str) for part in value)
    )


def _observe(session) -> _Observation:
    """Settle, read, classify -- in that order, always.

    The order is the safety property, not a convenience: ``state`` is the
    cheap poll and does not settle (X1's docstring), so a read taken before
    a settle sees a mid-paint screen, and a mid-paint screen can yield a
    plausible-wrong sector that passes the anchor check. Canon's screen
    understanding "operates only on a settled screen"; this function is
    where that precondition is actually met.

    ``settle()`` must answer literally ``True``, not merely something
    truthy, and the strictness is aimed at one specific adapter mistake.
    The port's method names deliberately mirror the settle layer's, which
    makes "forward the return value" the obvious implementation -- but
    ``settle.wait_until_settled`` returns ``(reason, elapsed)``, and
    ``("timeout", 8.0)`` is TRUTHY. A truthiness test would read a settle
    that timed out as a settle that succeeded, and then read the screen
    anyway. Anything that is not ``True`` fails closed.
    """
    if session.settle() is not True:
        return _Observation(failure=HALT_SETTLE_FAILED)
    screen = session.screen()
    if not _is_screen(screen):
        return _Observation(failure=HALT_SCREEN_UNREADABLE)
    full_text, prompt_line = screen
    return _Observation(
        klass=classify_screen(full_text, prompt_line),
        sector=read_current_sector(prompt_line),
        fenced=bool(session.is_driver_fenced()),
    )


def _gate(observation: _Observation) -> Optional[str]:
    """May the App press a key into this boundary? ``None`` means yes.

    Applied at EVERY boundary, which is what makes mid-run and entry-time
    STOP the same mechanism (``app-autopilot-model.md``: "there is no
    'we're already committed, push through' state"). Pure, so the whole
    refusal ladder is testable without a session at all.

    Order is a reporting choice, not a safety one -- every branch halts, so
    the run stops identically whichever fires. It is ordered most-sovereign
    first: a human holding the keyboard outranks anything on the screen,
    and a screen that could not be established outranks any claim about
    what it shows.
    """
    if observation.failure is not None:
        return observation.failure
    if observation.fenced:
        return HALT_FENCED
    # DECISIONS §A.2. Derived from `classify.NEVER_AUTO_ACTION_CLASSES`,
    # never restated -- a class added there is refused here the same day.
    if observation.klass in NEVER_AUTO_ACTION_CLASSES:
        return HALT_NEVER_AUTO_ACTION
    if observation.klass == "unknown":
        return HALT_UNRECOGNIZED_SCREEN
    return None


def _check_start_anchor(loop: Loop, read: Optional[SectorRead], force: bool) -> Optional[str]:
    """Canon's start-anchor guard as a 4-way decision. ``None`` means the
    world matches the recording and the first send may proceed.

    ``force`` is read in EXACTLY ONE branch, and that is the whole design.
    Canon waives the legacy no-anchor case and nothing else: "force only
    ever waives the nothing-to-check-against legacy case", because "forcing
    past a *detected* mismatch is the exact near-miss this guard exists to
    prevent". Any edit that moves ``force`` below the first branch has
    changed that, whatever it looks like.

    The other three branches are the trap the module docstring's table
    spells out: ``absent`` and ``unreadable`` are *not* "no anchor to
    check". They are a present precondition that reality declined to
    confirm -- canon's "(or can't be read at all)" -- and they halt
    unforceably, exactly like a mismatch.
    """
    if loop.start_anchor is None:
        # The recording captured no precondition. Nothing to disagree with,
        # so this is an artifact-level refusal, not a live surprise -- and
        # it is the one halt an explicit human override may waive.
        return None if force else HALT_START_ANCHOR_MISSING

    # From here on there IS a precondition, so every remaining answer is a
    # live claim about reality and force is irrelevant to all of them.
    #
    # `read is None` is unreachable through `replay_loop` (a boundary that
    # produced no read has already been stopped by the gate) but is a real
    # input to this function, which is called directly by its own tests.
    if read is None or read.outcome == OUTCOME_UNREADABLE:
        return HALT_CURRENT_SECTOR_UNREADABLE
    if read.outcome == OUTCOME_ABSENT:
        return HALT_CURRENT_SECTOR_ABSENT
    if read.outcome != OUTCOME_READ:
        # X1's vocabulary is closed today, so this is unreachable through a
        # genuine `SectorRead`. It is here because the failure it guards is
        # asymmetric: a fourth outcome added upstream would otherwise fall
        # into the comparison below and be decided by whatever `sector`
        # happened to hold. Fail closed toward the unreadable halt rather
        # than let an outcome this module has never heard of reach a
        # keystroke.
        return HALT_CURRENT_SECTOR_UNREADABLE

    # OUTCOME_READ. X1 guarantees `sector` is an int here (its
    # `__post_init__` pairs the two), so this is a comparison of two
    # numbers and not a comparison against a hole.
    return None if read.sector == loop.start_anchor else HALT_START_ANCHOR_MISMATCH


# ---------------------------------------------------------------------------
# The replay
# ---------------------------------------------------------------------------


def _trace(index: int, step: LoopStep, confirmed: bool, observed_class: Optional[str]) -> StepTrace:
    return StepTrace(
        index=index,
        input=step.input,
        wait_prompt=step.wait_prompt,
        expected_post_class=step.expected_post_class,
        confirmed=confirmed,
        observed_class=observed_class,
    )


def replay_loop(loop: Loop, session, *, force: bool = False) -> ReplayResult:
    """Replay one taught macro against a live session, one confirmed step
    at a time, halting the instant reality disagrees.

    ``loop`` is a :class:`~tw2002_aiclient.loops.loader.Loop` -- the
    loader's validated document, required as that exact type rather than
    accepted structurally. The type check is load-bearing rather than
    defensive: the loader froze ``steps`` into a tuple precisely because
    "validation is worthless if the thing validated can be rewritten
    between loading and pressing", and a look-alike object with a mutable
    ``steps`` would discard that guarantee at the last moment. It also
    refuses the archived shape (``replay_skill`` took a raw dict) rather
    than half-working on it.

    ``session`` implements :class:`ReplaySession`. It has no default: this
    module cannot acquire a way to press keys, only be handed one.

    ``force`` waives exactly one halt -- a macro with no recorded anchor
    (:data:`FORCEABLE_HALTS`). It cannot waive a mismatch, an absent read,
    or an unreadable one, and no argument here can enable a
    never-auto-action screen.

    Returns a :class:`ReplayResult` and does not raise for any game
    outcome; halting is the normal, correct answer whenever the world has
    moved. It raises only for a caller bug (a wrong ``loop`` type), and
    that raise costs zero bytes because it happens before the first
    observation.
    """
    if not isinstance(loop, Loop):
        raise TypeError(
            "replay_loop needs a loops.loader.Loop -- the validated, frozen document -- "
            f"got {type(loop).__name__}. Load it with load_loop() rather than passing "
            "raw JSON: the loader's validation is what makes these steps pressable."
        )

    traces: list[StepTrace] = []
    sends_issued = 0

    def halted(reason: str, at: int, anchor: Optional[SectorRead]) -> ReplayResult:
        return ReplayResult(
            outcome=OUTCOME_HALTED,
            loop_name=loop.name,
            steps=tuple(traces),
            sends_issued=sends_issued,
            reason=reason,
            halted_at=at,
            anchor_read=anchor,
        )

    # ---- boundary 0: the only boundary that also checks the anchor ----
    observation = _observe(session)
    anchor_read = observation.sector
    reason = _gate(observation)
    if reason is None:
        reason = _check_start_anchor(loop, anchor_read, force)
    if reason is not None:
        # `step_i = -1` -- canon's own marker for "nothing was sent".
        return halted(reason, BEFORE_FIRST_SEND, anchor_read)

    for index, step in enumerate(loop.steps):
        # THE ONE SEND. Everything above this line is why it is allowed to
        # happen; everything below is why the next one might not be.
        #
        # Counted BEFORE the call, not after: a send that raised may still
        # have reached the wire, and bytes on the wire cannot be un-sent.
        # A counter that only counts returns would under-report exactly the
        # case worth knowing about.
        sends_issued += 1
        # Literally `True`, for the reason `_observe` gives about `settle()`
        # and with a sharper edge here: `settle.send_and_confirm` returns
        # `(reason, elapsed, confirmed)`, and an adapter that forwarded that
        # tuple would make EVERY send read as confirmed -- a blind pump
        # through the whole macro, which is the exact failure canon's
        # send-and-confirm invariant exists to make impossible. Anything
        # that is not `True` is a send this module cannot call confirmed.
        confirmed = session.send_and_confirm(step.input, step.wait_prompt) is True
        if not confirmed:
            # Canon: an unconfirmed send is itself the surprise, and replay
            # "does not then try to classify a screen it already knows is
            # untrustworthy". So there is no observation here at all.
            traces.append(_trace(index, step, confirmed=False, observed_class=None))
            return halted(HALT_CONFIRM_FAILED, index, anchor_read)

        observation = _observe(session)
        reason = _gate(observation)
        if reason is None and observation.klass != step.expected_post_class:
            # An ordinary divergence: the screen is one the app can name,
            # it is simply not the one this step recorded. Checked AFTER
            # the gate so that landing on a money screen reports the
            # prohibition rather than a class mismatch -- and so that a
            # macro recorded with `expected_post_class: unknown` (3 steps
            # of the real archived corpus) halts on the novelty rather
            # than "matching" an unrecognized screen against itself.
            reason = HALT_POST_CLASS
        traces.append(_trace(index, step, confirmed=True, observed_class=observation.klass))
        if reason is not None:
            return halted(reason, index, anchor_read)

    return ReplayResult(
        outcome=OUTCOME_COMPLETED,
        loop_name=loop.name,
        steps=tuple(traces),
        sends_issued=sends_issued,
        anchor_read=anchor_read,
    )
