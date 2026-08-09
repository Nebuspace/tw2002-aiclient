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
* ``canon/engine/macros.md`` §"Start-anchor — refuse on context mismatch"
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

The two ways the human takes it back
------------------------------------
Canon asks for both at the same choke-point: "A per-step **abort
predicate** and **arm predicate** are checked at the same choke-point as
every other guard, so a human's STOP (or a disarm) halts an in-flight
chain within one send-step" (``app-autopilot-model.md`` §"Chain
Execution"). They are two port methods and two reason codes, not one:

* ``is_driver_fenced()`` -> ``human_attach_blocks_trainer`` -- somebody
  has the keyboard and is typing into the game right now.
* ``should_abort()`` -> ``operator_stop`` -- the run was stood down.
  Nobody is driving; the App simply stopped.

Collapsing them would save a branch and cost the operator the one thing
the STOP banner exists to tell them. It would also hand a driver an
attractive way to implement "stop": withdraw the App's own authority and
let the fence branch fire -- which reports an attach that never happened.
The predicates are separate here so that no driver has to choose between
stopping and telling the truth about why.

Neither is a cycle-boundary check. Both are read at EVERY boundary, which
is what makes canon's "within one send-step" literal rather than
aspirational, and what makes them work on a run that has exactly one
cycle. (X4's ``session/autoloop.py`` is the first driver to wire them.)

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

The stop-loss floor (X5) -- a run-loop rail, checked at THIS choke-point
-----------------------------------------------------------------------
``floor`` is an optional credit floor. It is **not** this module's policy:
like ``force``, and like the arm/abort predicates, it is a required
EXTERNAL input the run-loop supplies (``app-autopilot-model.md``
§"Arm-Confirm": the arm gate is "a required, external input to the loop,
not an internal self-check the loop could grant itself"). What this module
owns is the *check*, and it owns it for one reason: this is the only place
in the codebase where a send can be stopped **before** it happens. Canon
asks for exactly that placement -- "a below-floor balance STOPS before it
buys" (§"Chain Execution") -- and a floor enforced anywhere else would be a
floor checked after the money moved.

So the division mirrors ``should_abort()`` exactly: ``session/autoloop.py``
decides *whether a run is floored and at what number*; this module refuses
the send. It is re-read at EVERY boundary, not only at entry, because a
taught macro spends between boundaries and a once-at-launch check is a
floor that stops nothing after step 0. Boundary 0's check is
simultaneously canon's arm-confirm rail -- "a legitimate run instant-dies
rather than arming blind" -- and needs no separate code path to be that.

Fail-closed is the whole content of a stop-loss, so the ladder in
:func:`_check_floor` halts on every answer that is not an affirmative
above-floor reading: never observed (``credits_unknown``), observed too
long ago (``credits_stale``), an adapter that answered with something that
is not a :class:`~tw2002_aiclient.session.state_parser.CreditsSnapshot` at
all (``credits_unreadable``), or a genuine reading at or below the number
(``floor_reached``). There is no branch that proceeds on an unknown
balance, and none that can be reached with ``floor`` set and the port's
:meth:`ReplaySession.credits` unasked.

A run with **no** floor never calls :meth:`ReplaySession.credits` at all --
the archive's own rule, kept because it is what lets every port written
before this parameter existed keep working unchanged, and what makes
"a floor was requested" and "credits were consulted" the same event.

The turn-budget rail (WO-AUTOLOOP-TURN-BUDGET) -- same choke-point
--------------------------------------------------------------------
``turn_budget`` is an optional *remaining-turns floor*, checked here for
the same reason ``floor`` is: this is the only place a send can be refused
before it happens. It is **not** a cycle count and does not unlock
``cycles`` -- see "What this slice is NOT". The run-loop decides whether a
run is budgeted and at what number; this module refuses the send.

Fail-closed ladder mirrors :func:`_check_floor`: never observed
(``turns_unknown``), observed too long ago (``turns_stale``), adapter
answered with something that is not a :class:`~tw2002_aiclient.session.state_parser.TurnsSnapshot`
(``turns_unreadable``), or a genuine reading at or below the armed number
(``turn_budget_exhausted``). A run with no ``turn_budget`` never calls
:meth:`ReplaySession.turns`.

The hazard-halt rail (WO-AUTOLOOP-HAZARD-HALT) -- always on
-----------------------------------------------------------
Always checked at every boundary (not an optional arm flag). Three shapes:

* ``game_select`` classification → ``autopilot_game_select``
* known fighters aboard == 0 → ``fighters_zero``
* settle never-safe → already ``settle_failed`` / ``confirm_failed``
  (those codes *are* the settle-desync half of this rail)

Unknown fighters do **not** halt -- only a confirmed zero does. A port
without :meth:`ReplaySession.fighters` skips the zero check (capture is
best-effort); game_select and settle halves still fire.

What this slice is NOT
----------------------
There is still no cycle count *inside* this player — each call is one pass —
and that is a boundary, not an omission. With all four rails built,
``AutoLoopRunner`` (WO-AUTOLOOP-CYCLES) invokes this N times for a
``cycles=N`` / ``scope: repeating`` arm, getting canon's per-cycle
start-anchor re-check for free, exactly as the archived ``play_skill``
got it from ``replay_skill``.

Also absent, deliberately: no ledger rows (``macros.md`` §"Ledgering a
replay" -- ``actor=trainer``), no ``autoloop`` CLI verb, no daemon driver,
no wire serializer. Each belongs to a slice that owns its own surface.

Parameter placeholders (WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2)
------------------------------------------------------------------------
``macros.md`` §"Parameterization" wants a step's literal number to
generalize into a named replay-time binding, e.g. ``{qty}`` -> ``50`` on
one run, ``100`` on another. Until this WO neither side of that existed:
capture recorded literals only and this module sent ``step.input``
verbatim, whatever it looked like -- ``_apply_params`` was cited in this
very docstring as archive-only, absent from tip.

:func:`loader.param_placeholder_name` is the ONE syntax both sides of the
round trip share: a step's entire ``input`` is either an ordinary literal
(the overwhelming majority of every macro, including every one recorded
before this existed) or exactly ``{name}``, never a hybrid. Resolution
(:func:`_apply_params`) happens immediately before the send it gates, and
the binding rule is one sentence: an explicit ``params=`` override (this
call's own argument) outranks the macro's own recorded default
(``loop.params``, written by the recorder), which is what a caller gets
when it supplies nothing at all.

Validated ENTIRELY at entry, before the first observation, for every step
in the macro at once (:func:`_unbound_params`) -- not lazily at the send
that would need it. The reason is the same one the floor/turn_budget port-
capability checks already give: discovering an unresolvable placeholder at
step 5 would mean steps 0-4 already spent real turns and credits on a run
that can never finish, which is a strictly worse outcome than refusing to
start. This module never sends the literal text of an unresolved
placeholder -- that would be four-or-so live bytes nobody taught, the
exact blind-pump send-and-confirm exists to make impossible, one layer
earlier than the send itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Protocol

from ..halt_reasons import QUALIFIER_SEP, halt_reason_code, qualify as _qualify
from ..session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from ..session.hud_tracking import ProfitSnapshot
from ..session.state_parser import (
    OUTCOME_ABSENT,
    OUTCOME_READ,
    OUTCOME_UNREADABLE,
    CreditsSnapshot,
    FightersSnapshot,
    SectorRead,
    TurnsSnapshot,
    read_current_sector,
)
from .loader import Loop, LoopStep, param_placeholder_name

__all__ = [
    "CREDITS_STALE_MS",
    "FORCEABLE_HALTS",
    "HALT_ABORTED",
    "HALT_CONFIRM_FAILED",
    "HALT_CREDITS_STALE",
    "HALT_CREDITS_UNKNOWN",
    "HALT_CREDITS_UNREADABLE",
    "HALT_CURRENT_SECTOR_ABSENT",
    "HALT_CURRENT_SECTOR_UNREADABLE",
    "HALT_FENCED",
    "HALT_FLOOR_REACHED",
    "HALT_HAZARD_GAME_SELECT",
    "HALT_HAZARD_ZERO_FIGHTERS",
    "HALT_NEVER_AUTO_ACTION",
    "HALT_POST_CLASS",
    "HALT_PROFIT_STALE",
    "HALT_PROFIT_TARGET_REACHED",
    "HALT_PROFIT_UNKNOWN",
    "HALT_PROFIT_UNREADABLE",
    "HALT_REASONS",
    "HALT_SCREEN_UNREADABLE",
    "HALT_SETTLE_FAILED",
    "HALT_START_ANCHOR_MISMATCH",
    "HALT_START_ANCHOR_MISSING",
    "HALT_TURN_BUDGET_EXHAUSTED",
    "HALT_TURNS_STALE",
    "HALT_TURNS_UNKNOWN",
    "HALT_TURNS_UNREADABLE",
    "HALT_UNRECOGNIZED_SCREEN",
    "OUTCOME_COMPLETED",
    "OUTCOME_HALTED",
    "OUTCOMES",
    "QUALIFIER_SEP",  # re-exported; cross-module tests pin this name
    "ReplayResult",
    "ReplaySession",
    "StepTrace",
    "TURNS_STALE_MS",
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
# human-sovereignty preemption, the OTHER half -- see "The two ways the
# human takes it back" in the module docstring. Kept a separate code from
# HALT_FENCED because they are different events with different repairs:
# somebody is now typing into the game (fenced) vs. nobody is, the run was
# called off (aborted).
HALT_ABORTED = "operator_stop"
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
# depletion -- the balance is AT OR BELOW the floor the run was armed with.
# Canon names this code in `app-autopilot-model.md`'s own citation of the
# archived loop-player ("`floor_reached` / `credits_unknown`"), so it is
# carried verbatim rather than re-spelled.
HALT_FLOOR_REACHED = "floor_reached"
# desync -- canon's escalation catalog, verbatim, including its gloss:
# "the credits field ... could not be read; autopilot will not act on an
# unknown balance". Here that means no balance has EVER been observed.
HALT_CREDITS_UNKNOWN = "credits_unknown"
# desync -- also canon's catalog, verbatim: "the last-known credits value is
# too old to trust for a decision". Kept a SEPARATE code from
# `credits_unknown` because canon enumerates both and because they want
# different repairs: never-observed means the arm sequence never showed a
# balance, stale means it did and the run has since drifted away from it.
# (`action-safety-guards.md` compresses the pair into one spelling in one
# sentence; the catalog in `control-and-escalation.md` is the enumeration,
# and `cockpit/stopbanner.py` already carries a label for each.)
HALT_CREDITS_STALE = "credits_stale"
# desync -- the port answered `credits()` with something that is not a
# `CreditsSnapshot`. An ADAPTER fault rather than a game state, kept
# distinct for exactly the reason HALT_SCREEN_UNREADABLE is: "could not
# read" and "read, and it says nothing" want different repairs. This is the
# code a port that forwarded a raw `(balance, ts)` tuple would earn --
# every such tuple is truthy, and a truthiness test would have read one as
# a healthy balance.
HALT_CREDITS_UNREADABLE = "credits_unreadable"
# depletion -- remaining turns are AT OR BELOW the turn_budget the run was
# armed with. Mirror of floor_reached for the turn-budget rail
# (WO-AUTOLOOP-TURN-BUDGET): a remaining-turns floor, re-checked at every
# boundary, halt before the next send.
HALT_TURN_BUDGET_EXHAUSTED = "turn_budget_exhausted"
# desync -- no turn count has EVER been observed. Parallel to
# credits_unknown: arm-confirm fails closed rather than playing blind.
HALT_TURNS_UNKNOWN = "turns_unknown"
# desync -- last-known turn count is too old to trust for a send decision.
HALT_TURNS_STALE = "turns_stale"
# desync -- the port answered turns() with something that is not a
# TurnsSnapshot (adapter fault; never truthiness-tested).
HALT_TURNS_UNREADABLE = "turns_unreadable"
# hazard -- classified game_select; human owns the door letter. Catalog
# spelling from control-and-escalation.md, carried verbatim.
HALT_HAZARD_GAME_SELECT = "autopilot_game_select"
# hazard -- fighters aboard known and exactly zero (WO-AUTOLOOP-HAZARD-HALT).
HALT_HAZARD_ZERO_FIGHTERS = "fighters_zero"

# target-reached -- WO-BUILD-PROFIT-TARGET-HALT. Profit (credits delta from
# this daemon session's first strict balance, `Session.profit_snapshot()`)
# is AT OR ABOVE the target the run was armed with. A stop CONDITION, not a
# new autonomy grant or arming path -- an additional rail at the same
# send choke-point `HALT_FLOOR_REACHED` already occupies, mirroring its
# exact fail-closed shape (see `_check_profit_target`).
HALT_PROFIT_TARGET_REACHED = "profit_target_reached"
# desync -- no profit has EVER been observed. Mirror of credits_unknown:
# arm-confirm fails closed rather than playing blind on a target run.
HALT_PROFIT_UNKNOWN = "profit_unknown"
# desync -- last-known profit reading is too old to trust for a send
# decision. Mirror of credits_stale.
HALT_PROFIT_STALE = "profit_stale"
# desync -- the port answered profit() with something that is not a
# ProfitSnapshot (adapter fault; never truthiness-tested). Mirror of
# credits_unreadable.
HALT_PROFIT_UNREADABLE = "profit_unreadable"

HALT_REASONS = frozenset({
    HALT_SETTLE_FAILED,
    HALT_SCREEN_UNREADABLE,
    HALT_FENCED,
    HALT_ABORTED,
    HALT_NEVER_AUTO_ACTION,
    HALT_UNRECOGNIZED_SCREEN,
    HALT_START_ANCHOR_MISSING,
    HALT_START_ANCHOR_MISMATCH,
    HALT_CURRENT_SECTOR_ABSENT,
    HALT_CURRENT_SECTOR_UNREADABLE,
    HALT_CONFIRM_FAILED,
    HALT_POST_CLASS,
    HALT_FLOOR_REACHED,
    HALT_CREDITS_UNKNOWN,
    HALT_CREDITS_STALE,
    HALT_CREDITS_UNREADABLE,
    HALT_TURN_BUDGET_EXHAUSTED,
    HALT_TURNS_UNKNOWN,
    HALT_TURNS_STALE,
    HALT_TURNS_UNREADABLE,
    HALT_HAZARD_GAME_SELECT,
    HALT_HAZARD_ZERO_FIGHTERS,
    HALT_PROFIT_TARGET_REACHED,
    HALT_PROFIT_UNKNOWN,
    HALT_PROFIT_STALE,
    HALT_PROFIT_UNREADABLE,
})

# How old a balance may be and still gate a send. AP-13's number
# (`credits_stale_ms`, default 15s) and AP-13's own disclosure of what it
# buys: the reading "may predate the current cycle's last buy by up to
# `credits_stale_ms`", so this is a TIME backstop, not per-spend precision.
# A genuinely per-spend "confirmed since the last buy" gate belongs to the
# buy flow, which does not exist yet. Deliberately NOT exposed on the wire:
# a knob is only worth shipping once something enforces it per-spend, and
# the archive's own honesty note records that its CLI never threaded one
# either.
CREDITS_STALE_MS = 15_000

# Same window as credits, on purpose: both rails are "is this sticky reading
# still young enough to gate a send", and inventing a second number would
# let one rail go soft while the other stayed tight. Not on the wire.
TURNS_STALE_MS = CREDITS_STALE_MS

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

# WO-PLAYER-HALT-NEVER-AUTO-CLASS: the qualified-reason shape, `<code>:<detail>`.
#
# `HALT_REASONS` stays the closed vocabulary of CODES and is deliberately NOT
# exploded into every code x class pair -- that would turn a readable
# 16-member set into a combinatorial one that grows silently whenever
# `classify` gains a class, and the closed-vocabulary pin
# (`reported == HALT_REASONS`) would stop being readable by a human.
#
# Instead the code is what is validated and the detail travels alongside it.
#
# WO-HALT-QUALIFY-CONSOLIDATE: the encoder, decoder, and separator now live in
# `tw2002_aiclient.halt_reasons`. The note that stood here previously said the
# three lines were "duplicated rather than shared, because the alternative is
# either a new shared package for six lines or an import that drags the explore
# module into the loop player" -- a correct objection to the wrong two options.
# The shared module imports nothing from session/loops/cockpit/adapters, so it
# creates no such edge, and `sector_explore` no longer re-derives the shape.
#
# The three names below are RE-EXPORTED here on purpose: existing callers and
# tests import them from this module, and the local `_qualify` spelling is also
# what the AST comparison guard scans for when it derives which halt codes can
# carry a detail. Removing the aliases would break both.
# (imported at the top of this module -- see the import block.)

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
        the App stops pressing, whatever screen is showing.

        **An adapter must not wire this to ``ControlLock.is_driver_fenced()``
        alone.** That flag is set by ``take_human()`` only when an App
        *dispatch* held the driver slot (``_driving``), and a background
        run holds ``enter_auto_loop()`` instead -- so an attach during a
        loop leaves it ``False`` and this predicate would answer "not
        fenced" while a human types into the game. The authority a loop
        driver must re-read is its own exclusive hold; see
        ``session/autoloop.py``'s port for the wiring."""

    def should_abort(self) -> bool:
        """Has the run been called off? ``True`` halts the replay.

        The arm predicate's other face, and canon requires it at exactly
        this choke-point: "A per-step **abort predicate** and **arm
        predicate** are checked at the same choke-point as every other
        guard, so a human's STOP (or a disarm) halts an in-flight chain
        within one send-step" (``app-autopilot-model.md`` §"Chain
        Execution"), and "the runtime is armed by the human's confirmed
        decision and re-reads that arm state at its own send choke-point,
        so disarming (stopping) reaches an in-flight run within one step,
        not only at the next cycle boundary" (§"Arm-Confirm").

        Held APART from :meth:`is_driver_fenced` rather than folded into
        it, because the two produce different reason codes and an operator
        acts on the code: :data:`HALT_FENCED` says a human is at the
        keyboard right now, :data:`HALT_ABORTED` says the run was stood
        down and nobody is driving. A driver that implemented "stop" by
        yanking its own hold and letting the fence branch fire would
        report an attach that never happened -- a false claim on the one
        surface whose whole job is to say truthfully why the App stopped.

        Required, like every other method here: an adapter that omits it
        raises at boundary 0, before any send. A default-to-"not aborted"
        lookup would make a driver that forgot to wire its stop
        UNSTOPPABLE, which is the wrong direction for a predicate whose
        entire purpose is to end a run."""

    def credits(self) -> CreditsSnapshot:
        """What the runtime knows about the balance RIGHT NOW: a
        :class:`~tw2002_aiclient.session.state_parser.CreditsSnapshot`.

        Required **iff** the run was given a ``floor``; unreached, and
        therefore unnecessary, on an unfloored run. :func:`replay_loop`
        refuses a floor handed to a port that cannot answer this, at entry
        and before any observation, so "a floor was accepted" and "a floor
        can be enforced" are the same condition rather than two hopes.

        An I/O fact, not a decision. The port reports the last balance and
        HOW OLD it is; whether that age is fresh enough, and whether the
        number clears the floor, are decided here -- the same split of
        labour every other method on this protocol follows. An adapter over
        the daemon core implements this with ``Session.credits_snapshot()``.

        **Return the snapshot object, never the underlying pair.** The
        archived session exposed ``(last_credits, last_credits_ts)`` and
        forwarding that is the obvious adapter -- but a non-empty tuple is
        truthy whatever it holds, and ``(None, None)`` is the one that
        matters: a driver leaning on truthiness would read "never observed"
        as a healthy balance and blow straight through the floor. Anything
        that is not a ``CreditsSnapshot`` halts the run
        (:data:`HALT_CREDITS_UNREADABLE`); it is never interpreted."""

    def turns(self) -> TurnsSnapshot:
        """What the runtime knows about remaining turns RIGHT NOW: a
        :class:`~tw2002_aiclient.session.state_parser.TurnsSnapshot`.

        Required **iff** the run was given a ``turn_budget``; unreached on
        an unbudgeted run. :func:`replay_loop` refuses a budget handed to a
        port that cannot answer this, at entry, so "a budget was accepted"
        and "a budget can be enforced" stay the same condition.

        Return the snapshot object, never a bare int or ``(turns, ts)``
        pair — anything that is not a ``TurnsSnapshot`` halts
        (:data:`HALT_TURNS_UNREADABLE`). An adapter over the daemon core
        implements this with ``Session.turns_snapshot()``."""

    def fighters(self) -> FightersSnapshot:
        """Fighters aboard RIGHT NOW, as a
        :class:`~tw2002_aiclient.session.state_parser.FightersSnapshot`.

        Optional on ports that predate the hazard rail; when present, a
        confirmed zero halts ``fighters_zero``. Return the snapshot object,
        never a bare int."""

    def profit(self) -> ProfitSnapshot:
        """What the runtime knows about profit (credits delta from this
        daemon session's first strict balance) RIGHT NOW: a
        :class:`~tw2002_aiclient.session.hud_tracking.ProfitSnapshot`.

        Required **iff** the run was given a ``profit_target``; unreached
        on an untargeted run -- same split as :meth:`credits`.
        :func:`replay_loop` refuses a target handed to a port that cannot
        answer this, at entry, so "a target was accepted" and "a target
        can be enforced" stay the same condition.

        Return the snapshot object, never a bare int or ``(profit, ts)``
        pair -- anything that is not a ``ProfitSnapshot`` halts
        (:data:`HALT_PROFIT_UNREADABLE`). An adapter over the daemon core
        implements this with ``Session.profit_snapshot()``."""


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

    ``input`` is what was ACTUALLY sent -- for a parameterized step
    (``{qty}``-style) that is the resolved keystrokes, not the macro's own
    placeholder text (:func:`_apply_params`); every non-parameterized step
    (still the overwhelming majority) carries exactly ``step.input``,
    unchanged from before this rail existed.

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
        # WO-PLAYER-HALT-NEVER-AUTO-CLASS: validate the CODE, not the whole
        # string -- `never_auto_action:money_prompt` is the same halt as
        # `never_auto_action`, carrying which class refused. The closed
        # vocabulary is still closed: an unknown code raises exactly as
        # before, whether or not it arrives qualified.
        if self.reason is not None and halt_reason_code(self.reason) not in HALT_REASONS:
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

    ``credits`` is whatever the port answered, UNVALIDATED and deliberately
    untyped here -- an observation records what an adapter said, and
    :func:`_check_floor` is what decides whether that was an answer. It is
    ``None`` on an unfloored run, which is a different fact from an adapter
    answering ``None``, and the two never meet: this field is only ever read
    when a floor was requested.

    ``turns`` follows the same contract for the turn-budget rail.

    ``fighters`` is captured whenever the port answers ``fighters()`` --
    the hazard-halt zero-fighter check reads it. ``None`` means the port
    has no fighters method (skip that half), not "zero aboard".
    """

    klass: Optional[str] = None
    sector: Optional[SectorRead] = None
    fenced: bool = False
    aborted: bool = False
    failure: Optional[str] = None
    credits: object = None
    turns: object = None
    fighters: object = None
    profit: object = None


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


def _observe(
    session, *, want_credits: bool = False, want_turns: bool = False, want_profit: bool = False
) -> _Observation:
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
    # AFTER `screen()`, never before, and the order is load-bearing rather
    # than tidy: an adapter captures the balance off the render `screen()`
    # takes, so asking for credits first would answer from the PREVIOUS
    # boundary -- a reading from before the send this boundary is about to
    # gate. Asked at all only when a floor is in play (see the module
    # docstring), so every port written before this method existed keeps
    # working on an unfloored run. Same rule for turns / turn_budget.
    credits = session.credits() if want_credits else None
    turns = session.turns() if want_turns else None
    # Hazard rail: fighters are best-effort. A port without fighters()
    # skips the zero-fighter half; game_select + settle still fire.
    fighters = session.fighters() if callable(getattr(session, "fighters", None)) else None
    # Same "asked at all only when armed" rule as credits/turns -- a run
    # with no profit_target never calls profit().
    profit = session.profit() if want_profit else None
    return _Observation(
        klass=classify_screen(full_text, prompt_line),
        sector=read_current_sector(prompt_line),
        fenced=bool(session.is_driver_fenced()),
        aborted=bool(session.should_abort()),
        credits=credits,
        turns=turns,
        fighters=fighters,
        profit=profit,
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
    # The arm predicate, re-read at the send choke-point. Ordered below the
    # fence only for reporting: if a human attached AND the run was stood
    # down, "a human is at the keyboard" is the more sovereign fact and the
    # more urgent one for the operator to see.
    if observation.aborted:
        return HALT_ABORTED
    # DECISIONS §A.2. Derived from `classify.NEVER_AUTO_ACTION_CLASSES`,
    # never restated -- a class added there is refused here the same day.
    #
    # WO-PLAYER-HALT-NEVER-AUTO-CLASS: the reason carries WHICH never-auto
    # class refused. Bare `never_auto_action` is honest only while that set
    # has exactly one member; the set is explicitly designed to grow ("a
    # class added there is refused here the same day"), and on the day it
    # does, the bare reason stops saying which screen stopped the run. That
    # is the latent twin of the explore defect #213 fixed, so it is carried
    # now rather than after the ambiguity ships.
    #
    # The class comes from `observation`, never a literal: a hardcoded
    # `money_prompt` would be indistinguishable from this while the set has
    # one member, which is exactly the mutation the pins have to catch.
    if observation.klass in NEVER_AUTO_ACTION_CLASSES:
        return _qualify(HALT_NEVER_AUTO_ACTION, observation.klass)
    if observation.klass == "unknown":
        return HALT_UNRECOGNIZED_SCREEN
    return None


def _check_floor(credits, floor: Optional[int], stale_ms: int) -> Optional[str]:
    """May the App spend at this boundary? ``None`` means yes.

    Pure, so the whole stop-loss ladder is testable without a session, a
    clock, or a socket -- and so that every branch below can be reached
    directly rather than only through a scripted run.

    **Every path except one halts.** The single non-halting path requires
    all four of: a floor was set, the port answered with a real
    :class:`CreditsSnapshot`, that snapshot carries an affirmative reading,
    that reading is young enough, and the number is strictly above the
    floor. Anything else -- an absent history, an age past the window, an
    adapter that answered with a tuple, a balance at or below the line --
    stops the run. There is deliberately no "assume we're fine" branch,
    because a stop-loss that proceeds on an unknown balance is not a
    stop-loss (``action-safety-guards.md``: "an unknown or stale balance
    HALTs ... rather than arming an unbounded floor").

    Written as POSITIVE gates, never as ``if not fresh``. ``age_s`` is a
    float, and a NaN slipping in makes ``age > limit`` False -- reading as
    perfectly fresh, the fail-OPEN direction, on the one comparison whose
    whole job is to fail closed. ``CreditsSnapshot`` already rejects a NaN
    at construction; this re-checks because the two together are a property
    and either alone is only a defence.

    ``floor is None`` returns ``None`` immediately: an unfloored run has
    nothing to check and must not be made to depend on a balance it never
    asked about.
    """
    if floor is None:
        return None
    if not isinstance(credits, CreditsSnapshot):
        # Includes `None` (a driver that set a floor and forgot to wire the
        # port) and every tuple shape (all truthy). Never interpreted.
        return HALT_CREDITS_UNREADABLE
    if credits.outcome != OUTCOME_READ:
        # `absent` -- nothing has ever stated a balance. Canon's arm-confirm
        # rail lands here at boundary 0: "the arm sequence must have shown a
        # confirmed balance before a floored run will start, or a legitimate
        # run instant-dies rather than arming blind."
        return HALT_CREDITS_UNKNOWN
    age_s = credits.age_s
    fresh = (
        isinstance(age_s, (int, float))
        and not isinstance(age_s, bool)
        and math.isfinite(age_s)
        and 0 <= age_s <= stale_ms / 1000.0
    )
    if not fresh:
        return HALT_CREDITS_STALE
    balance = credits.balance
    if not isinstance(balance, int) or isinstance(balance, bool):
        # Unreachable through a genuine snapshot (its `__post_init__` pairs
        # the two), and here for the reason `_check_start_anchor`'s fourth
        # branch is: the failure it guards is asymmetric. A non-int reaching
        # the comparison below would be decided by whatever `>` does with
        # it, and on this field that is money.
        return HALT_CREDITS_UNREADABLE
    # Strictly above, matching the archived rail (`bal <= floor` halts): a
    # floor of 500 means "stop at 500", not "stop below 500".
    return None if balance > floor else HALT_FLOOR_REACHED


def _check_profit_target(profit, profit_target: Optional[int], stale_ms: int) -> Optional[str]:
    """May the App spend at this boundary, or has profit already met the
    target? ``None`` means yes, proceed.

    Structural twin of :func:`_check_floor`, mirrored deliberately
    (WO-BUILD-PROFIT-TARGET-HALT): an additional stop CONDITION at the
    same choke-point, not a new autonomy grant. The direction is inverted
    from the floor (a floor halts BELOW a number; a target halts AT OR
    ABOVE one), but the fail-closed ladder is identical -- every path
    except one halts. The single non-halting path requires all four of: a
    target was set, the port answered with a real :class:`ProfitSnapshot`,
    that snapshot carries an affirmative reading, that reading is young
    enough, and the number is strictly below the target. Anything else --
    an absent history, an age past the window, an adapter that answered
    with something else, a profit at or above the target -- stops the run.
    There is deliberately no "assume we're fine" branch, for the same
    reason `_check_floor` has none: a target-halt that proceeds on an
    unknown profit is not a target-halt.

    ``profit_target is None`` returns ``None`` immediately: an untargeted
    run has nothing to check and must not be made to depend on a profit
    reading it never asked about.
    """
    if profit_target is None:
        return None
    if not isinstance(profit, ProfitSnapshot):
        return HALT_PROFIT_UNREADABLE
    if profit.outcome != OUTCOME_READ:
        return HALT_PROFIT_UNKNOWN
    age_s = profit.age_s
    fresh = (
        isinstance(age_s, (int, float))
        and not isinstance(age_s, bool)
        and math.isfinite(age_s)
        and 0 <= age_s <= stale_ms / 1000.0
    )
    if not fresh:
        return HALT_PROFIT_STALE
    amount = profit.profit
    if not isinstance(amount, int) or isinstance(amount, bool):
        return HALT_PROFIT_UNREADABLE
    return HALT_PROFIT_TARGET_REACHED if amount >= profit_target else None


def _check_turn_budget(turns, turn_budget: Optional[int], stale_ms: int) -> Optional[str]:
    """May the App spend another turn at this boundary? ``None`` means yes.

    Pure, and a structural twin of :func:`_check_floor`: every path except
    one halts. The single non-halting path requires a budget was set, the
    port answered with a real :class:`TurnsSnapshot`, that snapshot carries
    an affirmative reading, that reading is young enough, and the remaining
    turn count is strictly above the armed floor. Anything else stops the
    run. There is deliberately no "assume we're fine" branch
    (``action-safety-guards.md``: a run whose turn budget is unknown fails
    closed).

    ``turn_budget is None`` returns ``None`` immediately: an unbudgeted run
    must not depend on a turn count it never asked about.
    """
    if turn_budget is None:
        return None
    if not isinstance(turns, TurnsSnapshot):
        return HALT_TURNS_UNREADABLE
    if turns.outcome != OUTCOME_READ:
        return HALT_TURNS_UNKNOWN
    age_s = turns.age_s
    fresh = (
        isinstance(age_s, (int, float))
        and not isinstance(age_s, bool)
        and math.isfinite(age_s)
        and 0 <= age_s <= stale_ms / 1000.0
    )
    if not fresh:
        return HALT_TURNS_STALE
    remaining = turns.turns
    if not isinstance(remaining, int) or isinstance(remaining, bool):
        return HALT_TURNS_UNREADABLE
    # Strictly above, matching the credit floor: a budget of 50 means
    # "stop at 50 remaining", not "stop below 50".
    return None if remaining > turn_budget else HALT_TURN_BUDGET_EXHAUSTED


def _check_hazard(observation) -> Optional[str]:
    """Hazard-halt rail (WO-AUTOLOOP-HAZARD-HALT). ``None`` means proceed.

    Always-on at every boundary after :func:`_gate`. Settle never-safe is
    already expressed as ``settle_failed`` / ``confirm_failed`` on other
    paths; this function covers game-select and confirmed zero fighters.
    """
    if observation.klass == "game_select":
        return HALT_HAZARD_GAME_SELECT
    fighters = observation.fighters
    if isinstance(fighters, FightersSnapshot) and fighters.outcome == OUTCOME_READ:
        count = fighters.fighters
        if isinstance(count, int) and not isinstance(count, bool) and count == 0:
            return HALT_HAZARD_ZERO_FIGHTERS
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
# Parameter placeholders -- see the module docstring's own section
# ---------------------------------------------------------------------------


def _resolve_param(name: str, defaults: Mapping[str, str], overrides: Mapping[str, str]) -> Optional[str]:
    """The one binding rule, as one function: an explicit override
    outranks the macro's own recorded default. ``None`` means neither
    side names this parameter at all -- unresolved, not "empty"."""
    if name in overrides:
        return overrides[name]
    return defaults.get(name)


def _unbound_params(loop: Loop, overrides: Mapping[str, str]) -> list[str]:
    """Every parameter this macro's steps reference that neither
    ``overrides`` nor ``loop.params`` can resolve -- checked across ALL
    steps at once, so a macro missing a LATE parameter refuses before step
    0 rather than stranding mid-run with earlier steps already sent (see
    the module docstring's "Parameter placeholders" section)."""
    # A comprehension, not a `for`: `test_no_run_loop_snuck_in` asserts
    # exactly one loop statement in this whole module (the replay's own
    # step walk) as a structural proof that no repetition snuck in beside
    # it. This is validation, not repetition, so it earns no exception --
    # a comprehension makes that true at the AST level, not just by intent.
    names = (param_placeholder_name(step.input) for step in loop.steps)
    return [name for name in names if name is not None and _resolve_param(name, loop.params, overrides) is None]


def _apply_params(raw_input: str, defaults: Mapping[str, str], overrides: Mapping[str, str]) -> str:
    """The keystrokes to actually send for one step.

    A step whose ``input`` is not a ``{name}`` placeholder resolves to
    itself, unchanged -- zero new behaviour for every macro that predates
    this rail. A placeholder resolves through :func:`_resolve_param`.

    :func:`replay_loop` proves every step's placeholder resolvable BEFORE
    the first observation (:func:`_unbound_params`); the assertion below is
    belt-and-suspenders against a FUTURE edit that let an unresolvable one
    through anyway, not the enforcement itself -- sending the literal text
    ``"{qty}"`` would be live bytes nobody taught, and asserting here is
    cheaper than discovering it against a real socket.
    """
    name = param_placeholder_name(raw_input)
    if name is None:
        return raw_input
    resolved = _resolve_param(name, defaults, overrides)
    assert resolved is not None, (
        f"step input {raw_input!r} names parameter {name!r}, which replay_loop's "
        "own entry validation should already have refused -- resolving it here "
        "anyway would send the literal placeholder text"
    )
    return resolved


# ---------------------------------------------------------------------------
# The replay
# ---------------------------------------------------------------------------


def _trace(
    index: int, step: LoopStep, resolved_input: str, confirmed: bool, observed_class: Optional[str]
) -> StepTrace:
    return StepTrace(
        index=index,
        input=resolved_input,
        wait_prompt=step.wait_prompt,
        expected_post_class=step.expected_post_class,
        confirmed=confirmed,
        observed_class=observed_class,
    )


def replay_loop(
    loop: Loop,
    session,
    *,
    force: bool = False,
    floor: Optional[int] = None,
    credits_stale_ms: int = CREDITS_STALE_MS,
    turn_budget: Optional[int] = None,
    turns_stale_ms: int = TURNS_STALE_MS,
    profit_target: Optional[int] = None,
    profit_stale_ms: int = CREDITS_STALE_MS,
    params: Optional[Mapping[str, str]] = None,
) -> ReplayResult:
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
    never-auto-action screen. It does not touch the floor or turn budget:
    those are live readings, not recording artifacts.

    ``floor`` is an optional credit floor, re-checked at EVERY boundary --
    see the module docstring. ``None`` (the default) means no floor was
    requested and :meth:`ReplaySession.credits` is never called. A floor
    handed to a port that cannot answer credits raises **at entry**, before
    any observation: accepting a floor this run could not enforce is the one
    failure the rail exists to make impossible, so it is refused where it
    cannot be missed rather than discovered as an ``AttributeError`` at the
    first boundary.

    ``turn_budget`` is an optional remaining-turns floor (WO-AUTOLOOP-
    TURN-BUDGET), re-checked at every boundary the same way. ``None`` means
    :meth:`ReplaySession.turns` is never called. A budget against a port
    that cannot answer turns raises at entry.

    ``credits_stale_ms`` / ``turns_stale_ms`` are how old a sticky reading
    may be and still gate a send. A non-positive window is refused at entry.

    ``profit_target`` is an optional ADDITIONAL stop -- halt the instant
    profit (credits delta from this daemon session's first strict balance,
    see :meth:`ReplaySession.profit`) reaches or exceeds it, mirroring
    ``floor``'s exact shape with the direction inverted. ``None`` means
    :meth:`ReplaySession.profit` is never called. A target against a port
    that cannot answer profit raises at entry, same as an unenforceable
    floor. ``profit_stale_ms`` is its staleness window, same rule as
    ``credits_stale_ms``.

    ``params`` is an optional name -> keystrokes mapping that OVERRIDES the
    macro's own recorded defaults (``loop.params``) for any ``{name}``
    placeholder step (module docstring, "Parameter placeholders"). ``None``
    (the default) means every placeholder falls back to its recorded
    default, so a caller that never asks for this behaves exactly as if the
    macro had none. Every placeholder across every step must resolve --
    through ``params`` or through ``loop.params``, either is enough -- or
    this raises **at entry**, before any observation, the same posture as
    an unenforceable floor: discovering a missing parameter at step 5 would
    mean steps 0-4 already spent real turns and credits on a run that can
    never finish.

    Returns a :class:`ReplayResult` and does not raise for any game
    outcome; halting is the normal, correct answer whenever the world has
    moved. It raises only for a caller bug (a wrong ``loop`` type, an
    unenforceable floor or budget, an unresolvable parameter), and every
    such raise costs zero bytes because it happens before the first
    observation.
    """
    if not isinstance(loop, Loop):
        raise TypeError(
            "replay_loop needs a loops.loader.Loop -- the validated, frozen document -- "
            f"got {type(loop).__name__}. Load it with load_loop() rather than passing "
            "raw JSON: the loader's validation is what makes these steps pressable."
        )
    if floor is not None:
        # The type check is the rail, not politeness. `True` is an int in
        # Python and would arm a floor of 1; a float would compare fine and
        # then never be the number anyone typed.
        if isinstance(floor, bool) or not isinstance(floor, int):
            raise TypeError(
                "replay_loop's floor is a credit balance and must be an int -- "
                f"got {type(floor).__name__}. A floor that is not a number is a "
                "floor nothing can enforce."
            )
        if not callable(getattr(session, "credits", None)):
            raise TypeError(
                "replay_loop was given floor=%r but this port cannot observe credits "
                "(no callable credits()). A floor accepted here would be a flag that "
                "reads as a safety feature and stops nothing -- refused instead."
                % (floor,)
            )
        if not isinstance(credits_stale_ms, int) or isinstance(credits_stale_ms, bool):
            raise TypeError(
                "credits_stale_ms must be an int (milliseconds) -- got "
                f"{type(credits_stale_ms).__name__}."
            )
        if credits_stale_ms <= 0:
            raise ValueError(
                f"credits_stale_ms must be positive -- got {credits_stale_ms}. A "
                "non-positive window rejects every reading, so every floored run "
                "would instant-halt `credits_stale` -- safe, but a rail that always "
                "fires is a rail nobody can use, and it should be refused where the "
                "caller can see it rather than at the first boundary."
            )
    if turn_budget is not None:
        if isinstance(turn_budget, bool) or not isinstance(turn_budget, int):
            raise TypeError(
                "replay_loop's turn_budget is a remaining-turns floor and must be an "
                f"int -- got {type(turn_budget).__name__}."
            )
        if not callable(getattr(session, "turns", None)):
            raise TypeError(
                "replay_loop was given turn_budget=%r but this port cannot observe "
                "turns (no callable turns()). A budget accepted here would be a "
                "flag that reads as a safety feature and stops nothing -- refused "
                "instead." % (turn_budget,)
            )
        if not isinstance(turns_stale_ms, int) or isinstance(turns_stale_ms, bool):
            raise TypeError(
                "turns_stale_ms must be an int (milliseconds) -- got "
                f"{type(turns_stale_ms).__name__}."
            )
        if turns_stale_ms <= 0:
            raise ValueError(
                f"turns_stale_ms must be positive -- got {turns_stale_ms}."
            )
    if profit_target is not None:
        if isinstance(profit_target, bool) or not isinstance(profit_target, int):
            raise TypeError(
                "replay_loop's profit_target is a credit amount and must be an "
                f"int -- got {type(profit_target).__name__}."
            )
        if not callable(getattr(session, "profit", None)):
            raise TypeError(
                "replay_loop was given profit_target=%r but this port cannot "
                "observe profit (no callable profit()). A target accepted here "
                "would be a flag that reads as a safety feature and stops "
                "nothing -- refused instead." % (profit_target,)
            )
        if not isinstance(profit_stale_ms, int) or isinstance(profit_stale_ms, bool):
            raise TypeError(
                "profit_stale_ms must be an int (milliseconds) -- got "
                f"{type(profit_stale_ms).__name__}."
            )
        if profit_stale_ms <= 0:
            raise ValueError(
                f"profit_stale_ms must be positive -- got {profit_stale_ms}."
            )
    if params is not None and (
        not isinstance(params, Mapping)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in params.items())
    ):
        raise TypeError(
            "replay_loop's params must be a mapping of parameter name -> "
            f"keystrokes to send -- got {type(params).__name__}."
        )
    overrides: Mapping[str, str] = params if params is not None else {}
    # Every step's placeholder, checked NOW rather than at the send that
    # would need it -- see the module docstring's "Parameter placeholders"
    # section for why a late unbound parameter is refused before step 0
    # rather than discovered after earlier steps already spent real turns
    # and credits on a run that can never finish.
    unbound = _unbound_params(loop, overrides)
    if unbound:
        names = sorted(set(unbound))
        raise ValueError(
            f"replay_loop cannot resolve parameter{'s' if len(names) != 1 else ''} "
            f"{names} in macro {loop.name!r} -- pass params={{...}} or record a "
            "default for each (loops/recorder.py's step(param=...)); discovering "
            "this mid-run would mean earlier steps already sent while a later "
            "one could not be"
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

    want_credits = floor is not None
    want_turns = turn_budget is not None
    want_profit = profit_target is not None

    # ---- boundary 0: the only boundary that also checks the anchor ----
    observation = _observe(
        session, want_credits=want_credits, want_turns=want_turns, want_profit=want_profit
    )
    anchor_read = observation.sector
    reason = _gate(observation)
    if reason is None:
        reason = _check_hazard(observation)
    if reason is None:
        # The floor sits between the gate and the anchor, and the placement
        # is a REPORTING choice like every other order in this ladder: the
        # gate's facts (a human at the keyboard, a screen that could not be
        # established) outrank a balance, and the floor is grouped with the
        # gate because both are re-read at every boundary while the anchor
        # is a one-time pre-flight. Every branch halts, so nothing is less
        # safe whichever fires first.
        reason = _check_floor(observation.credits, floor, credits_stale_ms)
    if reason is None:
        reason = _check_turn_budget(observation.turns, turn_budget, turns_stale_ms)
    if reason is None:
        reason = _check_profit_target(observation.profit, profit_target, profit_stale_ms)
    if reason is None:
        reason = _check_start_anchor(loop, anchor_read, force)
    if reason is not None:
        # `step_i = -1` -- canon's own marker for "nothing was sent".
        return halted(reason, BEFORE_FIRST_SEND, anchor_read)

    for index, step in enumerate(loop.steps):
        # Resolved BEFORE the send it gates, never after -- see the module
        # docstring's "Parameter placeholders" section. `replay_loop`'s own
        # entry validation has already proven every placeholder resolvable,
        # so this cannot itself halt; it is the SUBSTITUTION step, not a
        # second gate.
        resolved_input = _apply_params(step.input, loop.params, overrides)
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
        confirmed = session.send_and_confirm(resolved_input, step.wait_prompt) is True
        if not confirmed:
            # Canon: an unconfirmed send is itself the surprise, and replay
            # "does not then try to classify a screen it already knows is
            # untrustworthy". So there is no observation here at all.
            traces.append(_trace(index, step, resolved_input, confirmed=False, observed_class=None))
            return halted(HALT_CONFIRM_FAILED, index, anchor_read)

        observation = _observe(
            session, want_credits=want_credits, want_turns=want_turns, want_profit=want_profit
        )
        reason = _gate(observation)
        if reason is None:
            reason = _check_hazard(observation)
        if reason is None:
            # Re-checked here, not only at boundary 0, and this call is the
            # difference between a stop-loss and a decoration: a taught macro
            # spends BETWEEN boundaries, so a floor checked once at launch
            # would watch the balance cross the line and press on. Boundary
            # i+1 is step i+1's pre-send check (see "Boundaries, not phases"),
            # so refusing here refuses the next send before it happens.
            reason = _check_floor(observation.credits, floor, credits_stale_ms)
        if reason is None:
            reason = _check_turn_budget(observation.turns, turn_budget, turns_stale_ms)
        if reason is None:
            reason = _check_profit_target(observation.profit, profit_target, profit_stale_ms)
        if reason is None and observation.klass != step.expected_post_class:
            # An ordinary divergence: the screen is one the app can name,
            # it is simply not the one this step recorded. Checked AFTER
            # the gate so that landing on a money screen reports the
            # prohibition rather than a class mismatch -- and so that a
            # macro recorded with `expected_post_class: unknown` (3 steps
            # of the real archived corpus) halts on the novelty rather
            # than "matching" an unrecognized screen against itself.
            reason = HALT_POST_CLASS
        traces.append(_trace(index, step, resolved_input, confirmed=True, observed_class=observation.klass))
        if reason is not None:
            return halted(reason, index, anchor_read)

    return ReplayResult(
        outcome=OUTCOME_COMPLETED,
        loop_name=loop.name,
        steps=tuple(traces),
        sends_issued=sends_issued,
        anchor_read=anchor_read,
    )
