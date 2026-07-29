"""Read the two game-state facts a safety rail needs off a settled screen:
the ship's CURRENT SECTOR (the precondition every macro replay re-checks
before it presses anything) and its CREDITS BALANCE (the number the
stop-loss floor halts on).

WO-P2-G4-X1 (sector) and WO-P2-G4-X5 (credits). Pure and deterministic:
this module takes text and returns a verdict. It holds no session, opens
no socket, and cannot send a keystroke (a test enforces that by AST scan
rather than asserting it). Comparing the answer to a macro's
``start_anchor`` or to a run's floor, and deciding what to do about the
comparison, belongs to the player (X3) and is deliberately absent here.

Canon
-----
* ``canon/engine/macros.md`` §"Start-anchor — refuse on context mismatch":
  before the first send of *every* replay invocation, replay "reads the
  current sector and validates it against the macro's ``start_anchor``".
  An anchor that is present but whose current sector "differs (or can't be
  read at all)" is a halt, and canon states outright that this halt is
  **not bypassable by force** -- "forcing past a *detected* mismatch is the
  danger itself". That sentence is why this module exists and why it is
  built to refuse rather than to answer.
* ``canon/engine/screen-understanding.md`` §"The Unknown Is First-Class":
  "The layer **never fabricates** a value to fill a hole... an unreadable
  sector is absent, not a guess." The rule being drawn there is *absent
  rather than GUESS*; this module keeps that rule and adds the distinction
  the sentence does not make -- see "Three outcomes" below.
* ``canon/engine/screen-understanding.md`` §"The Last-Match Invariant":
  every extracted field anchors to the LAST match in the buffer, never the
  first, because pyte emulates a fixed 80x25 grid with no scrollback and a
  stale value can sit *above* the live one.
* ``canon/architecture/cli-verbs.md §"Session primitives"``: ``state`` is "parsed structured
  game-state only", ``read-only``.
* ``canon/research/tw2002-screen-patterns.md`` P-SETTLE-LINE: "a stale copy
  of the target text elsewhere on the grid still hits. Do not treat
  whole-screen regex success as proof the *live* prompt matched." This
  module takes that further than a scoping convention -- see "One source".

Three outcomes, never two
-------------------------
"the ship is in sector N", "this screen makes no claim about where the ship
is", and "this screen started to say and I could not finish reading it" are
three different facts, and the consumer -- a player deciding whether it may
press keys into a live economy -- can act on only one of them.

* ``read``       -- a sector number, established from a live source.
* ``absent``     -- the screen was examined in full and carries no
  current-sector claim at all. A genuine negative about the SCREEN, never a
  claim that the ship is nowhere.
* ``unreadable`` -- a current-sector claim is present in damaged form (or
  the input was not a screen), so nothing was established. The number may
  well be sitting in the cells we could not resolve.

Collapsing the third into the second is the defect this repo has now fixed
five times (``credentials`` / ``env.load_dotenv`` / ``get_password`` /
``daemon_alive`` / ``loops.loader``), and ``Path.exists()`` was the vehicle
for most of them. There is no filesystem here, so the vehicle this time is
the archive's own shape: ``parse_state()`` returned a dict and a caller
wrote ``parse_state(text).get("sector")``, which answers ``None`` for "no
sector on this screen" and ``None`` for "the screen was unparseable" with
no way to tell them apart -- and the archive's own
``protocol._dispatch_record_start`` stamped exactly that ``None`` into a
macro's ``start_anchor``.

**There is deliberately no key you can ``.get()`` for a bare number.** The
verdict is a :class:`SectorRead` whose ``sector`` is an ``int`` if and only
if ``outcome == OUTCOME_READ``, enforced in ``__post_init__`` -- structural,
not conventional. On the wire the same shape holds: ``state.sector`` is an
OBJECT carrying an outcome, and the ``sector`` key is omitted rather than
set to ``null`` on the two non-read outcomes, so a caller reaching straight
for the number fails loudly instead of silently reading a hole (the same
omit-don't-mark discipline ``protocol._status_response`` and
``protocol._login_failure_response`` state for their withheld fields).

One source, and why the obvious second one is refused
-----------------------------------------------------
The only source admitted here is the **command-prompt sector bracket** on
the screen's own **current prompt line**: ``Command [TL=…]:[NNNN]`` (and the
computer subsystem's ``Computer command [TL=…]:[NNNN]``, which the same
pattern covers -- ``classify.py``'s established "superset" precedent). It is
the one thing on a TW2002 screen that *definitionally* names where the ship
is right now, and canon adopted it for exactly this reason: the arrival
burst on a port sector can scroll the status display off a fixed 25-row grid
with no scrollback, and "the same-screen prompt anchor is present exactly
where a cross-screen anchor would have gone stale"
(``screen-understanding.md``).

Scoping it to the current prompt line is a second, independent narrowing,
and it is structural rather than a convention: this function is handed the
prompt line and **cannot see the rest of the grid**, so no amount of stale
or forged body content can reach it. That closes the whole-screen half of
the archive's documented forged-last-match residual for this field. It does
not close all of it -- a forged fragment rendering *after* the genuine
prompt would become the prompt line -- so the residual is NARROWED, not
retired, and it stays owned by ``screen-understanding.md``'s single
anchor-to-live-prompt hardening item.

The obvious second source -- the ``Sector : N`` status-display line the
archive's ``_SECTOR_RE`` matched -- is **not admitted**, and the omission is
the load-bearing decision in this module rather than an oversight:

* Canon never claims that line means "where the ship is now". It calls it a
  sector *display*. On an arrival screen the two coincide; that they always
  do is an assumption, not a documented fact.
* This repo's own ``tests/fixtures/warp_confirm_prompt.txt`` is the
  counter-example, and it passes every provenance gate the archive built:
  ``Sector  : 3034 in uncharted space.`` followed immediately by
  ``Warps to Sector(s) :`` (so ``is_genuine_sector_status()`` returns True)
  under a ``Do you really want to warp there? (Y/N)`` prompt --
  ``classify.py``'s ``warp_confirm``, a mid-transaction stall. Whether 3034
  is where the ship IS or where it is about to GO is not settled by canon,
  by the fixture, or by anything else in this tree. A computer sector
  ``D``isplay of a remote sector is the same shape with the same ambiguity.
* The archive itself moved away from that line for the current-sector
  question: ``sector_from_command_prompt()`` was introduced to REPLACE the
  status-line anchor for the world-model write path.
* The error directions are wildly asymmetric. A missing read halts a replay
  -- canon's normal, correct outcome. A WRONG read satisfies the start-anchor
  check and replays a macro from the wrong sector, which is verbatim the live
  incident (``macros.md``: "warped the ship off into a stale sector") the
  guard was written to prevent.

The cost is disclosed, not hidden: on a CLASSIC-shape TWGS server whose
prompt carries no ``[NNNN]`` bracket at all (``Command
[TL=00753:0/0/0/850] (?=Help)? :``), the current sector is never readable
here and every anchored replay halts. Canon already accepts that shape of
trade-off for this anchor -- "a fail-closed COVERAGE trade-off (a missed
write, never a wrong one)" -- and the live target server uses the bracketed
form. A consumer can tell that case apart from any other ``absent`` without
new machinery, because the ``state`` response carries ``classification``
beside this verdict: ``main_command`` + ``absent`` is precisely "a command
prompt that states no sector". Widening this module to the status line is a
canon question (does ``Sector : N`` on a settled non-``warp_confirm`` screen
mean *current*?) and wants a live capture of the warp-confirm screen to
settle it -- not a drive-by regex.

The credits balance (X5), and the one source it will not accept
---------------------------------------------------------------
:func:`read_credits_balance` answers the SAME three outcomes about a
different field, and it exists for the stop-loss rail
(``canon/doctrine/action-safety-guards.md`` §"Structural rails": "A credit
floor halts the loop, read from the *strict* last-known confirmed balance
and fail-closed"). "Strict" is the load-bearing word and it is the entire
reason this function is not a two-line regex:

``canon/research/archive-port-patterns.md`` AP-13 states the rule outright
-- *"Using ``parse_state()`` for a cash-floor stop-loss means the stop-loss
can be defeated by a price quote on the wrong screen -- exactly what
happened live before this was fixed."* The archive's looser ``credits``
field matched a bare ``(\\d[\\d,]*)\\s+credits`` anywhere on the grid, and a
port's own haggle sentence (``We'll buy them for 2,214 credits.``) satisfies
that just as well as a real balance. A haggle screen is *made of* those
sentences, so the loose form does not merely risk a wrong number -- it
reliably reports the wrong number on precisely the screens where money is
being spent. **That pattern is therefore absent from this module, and the
pin is enforced against the COMPILED patterns rather than the source text:
a test walks every ``re.Pattern`` this module defines and asserts none of
them matches a real captured price-quote line.** (Source-text scanning
would trip over this very paragraph, which has to name the shape to explain
it -- the docstrings-are-nodes trap.)

Two shapes are accepted, both of which state a balance and neither of which
a price quote can wear:

* ``You have N credits`` -- the classic post-transaction / info line.
* ``Credits : N`` (label-first, ``:`` or ``=``) -- the ship-info ``I``
  screen.

Both are content anchors (they live in the body, not on the prompt line),
so unlike the sector bracket they are whole-screen, LAST-match per canon's
Last-Match Invariant -- and the last match is taken by POSITION across both
patterns together, not by trying one pattern's matches before the other's.
The archive tried ``You have`` first and fell back to the label form only
when it found none, which is a PRIORITY order wearing a last-match's
clothes: a stale ``You have`` line up the grid outranked a fresher
``Credits :`` below it. (The same priority/position confusion the archive's
own ``parse_haggle`` had to fix for quotes: "position-sorted, not
regex-priority-sorted".)

``[ \\t]`` throughout, never ``\\s`` -- the sector half of this module
documents why (the archive's ``\\s+`` "crossed newlines and forged
turns_left from the prior line's sector id"), and here the input is a whole
multi-line screen by contract, so it is a live hazard rather than
belt-and-braces.

**The damage check is narrower than the read, deliberately.** A label-first
claim that opened and did not resolve (``Credits    :`` with the number not
yet painted) is ``unreadable``. A half-painted ``You have 100,4`` has no
prefix that is unambiguously a balance -- ``You have 3 fighters`` wears the
same opening -- so it is reported ``absent``, and that is a disclosed
narrowing rather than a claim of completeness. Nothing is lost safely-wise:
both non-read outcomes leave :meth:`Session.observe_credits`'s sticky value
untouched, the previous reading keeps aging, and the floor's staleness gate
is what catches a screen that has stopped stating a balance.

**FORGED-BALANCE RESIDUAL, inherited and not closed here.** Both patterns
are unanchored last-match over the whole grid, so an in-band ``You have N
credits`` authored by another player (chat, broadcast, hail) landing after
the genuine line overrides it -- in EITHER direction, and the *inflating*
direction is the dangerous one: ``loops/player.py``'s ``_check_floor`` halts
only when ``balance > floor`` is false, so a forged HIGH number reads as
comfortably above the floor and the run proceeds while the real balance may
already be below it -- the stop-loss defeated, not merely dodged. It is
also self-sustaining rather than a one-shot risk: ``Session.observe_credits``
re-stamps the sticky reading's age on every settled screen that matches, so
an attacker repeating the forge (a looped broadcast) keeps the balance
looking fresh and the staleness gate never fires either. The *deflating*
direction only trips a spurious ``floor_reached`` halt -- safe-by-design,
since halting is this module's correct failure mode, but a real availability
cost, not a masked balance. Canon knows this and gates on it: "In
multiplayer, where a hostile server frame could forge a balance line, arming
this stop-loss carries a documented forged-balance caveat and its own
arming gate" (``action-safety-guards.md``). SOLO-safe today; **this repo has
no solo/multiplayer signal to gate on, so that arming gate is NOT built here
and is owed.**

What is NOT checked
-------------------
The VALUE is not range-checked, deliberately and symmetrically with
``loops.loader._validate_anchor``, which declines to range-check the
recorded ``start_anchor`` for the same reason: "a wrong anchor is caught
live by the start-anchor check and halts safely, so inventing a sector
range here would reject real macros to duplicate a guard that already
exists." Inventing a galaxy size in one of the two halves of a comparison
and not the other is how the halves stop agreeing.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "OUTCOME_ABSENT",
    "OUTCOME_READ",
    "OUTCOME_UNREADABLE",
    "OUTCOMES",
    "REASON_DAMAGED_COMMAND_PROMPT",
    "REASON_DAMAGED_CREDITS_LABEL",
    "REASON_NOT_TEXT",
    "REASON_SESSION_DISCONNECTED",
    "REASONS",
    "SNAPSHOT_OUTCOMES",
    "SOURCE_COMMAND_PROMPT",
    "SOURCE_CREDITS_LABEL",
    "SOURCE_YOU_HAVE_CREDITS",
    "SOURCES",
    "CreditsRead",
    "CreditsSnapshot",
    "SectorRead",
    "credits_never_observed",
    "read_credits_balance",
    "read_current_sector",
    "read_warps_from_sector_status",
    "sector_unreadable",
    "sector_wire",
]


# ---------------------------------------------------------------------------
# Closed vocabularies -- the whole reason this answer is safe on the wire
# ---------------------------------------------------------------------------
#
# Every non-numeric value this module can put into a response is drawn from
# one of the three frozensets below. That is what makes `sector_wire()`
# bounded BY CONSTRUCTION rather than by inspection: there is no code path
# that can place a slice of the screen into the answer, because there is no
# string in the answer that did not come from here. A test enumerates the
# wire dict over hostile screens (including one whose prompt line IS a
# credential) and asserts every value is an `int` or a member of these sets.

OUTCOME_READ = "read"
OUTCOME_ABSENT = "absent"
OUTCOME_UNREADABLE = "unreadable"
OUTCOMES = frozenset({OUTCOME_READ, OUTCOME_ABSENT, OUTCOME_UNREADABLE})

SOURCE_COMMAND_PROMPT = "command_prompt"
# The two accepted credits shapes, named individually rather than folded
# into one `credits` source: an operator reading a halt wants to know
# WHICH line the balance came off, and the two have different provenance
# (a post-transaction message vs. the ship-info screen).
SOURCE_YOU_HAVE_CREDITS = "you_have_credits"
SOURCE_CREDITS_LABEL = "credits_label"
# The three accepted turn-count shapes, named individually for the same
# reason the two credits shapes are: an operator looking at a turns cell
# wants to know WHICH line produced it, and on this field the answer decides
# how much to trust it. `turn_count_prompt` is the CLASSIC-server `TL=`
# body; the other two are body statements this server actually prints.
SOURCE_TURN_COUNT_PROMPT = "turn_count_prompt"
SOURCE_TURNS_LEFT_NARRATIVE = "turns_left_narrative"
SOURCE_TURNS_LEFT_LABEL = "turns_left_label"
SOURCES = frozenset({
    SOURCE_COMMAND_PROMPT,
    SOURCE_YOU_HAVE_CREDITS,
    SOURCE_CREDITS_LABEL,
    SOURCE_TURN_COUNT_PROMPT,
    SOURCE_TURNS_LEFT_NARRATIVE,
    SOURCE_TURNS_LEFT_LABEL,
})

# A damaged anchor: the prompt line opened a sector bracket and the number
# did not resolve out of it. Reachable in ordinary operation, not merely
# defensive -- `state` is the CHEAP-POLL verb and does not settle (see
# `protocol._state_response`), so a poll landing mid-paint sees exactly this.
REASON_DAMAGED_COMMAND_PROMPT = "damaged_command_prompt"
# Handed something that is not a screen line at all (bytes, None, a dict).
REASON_NOT_TEXT = "not_text"
# Set by the caller, never by the parser: the socket is down, so the pyte
# grid is a FROZEN last-seen frame and its bracket names where the ship was,
# not where it is. See `protocol._state_response`.
REASON_SESSION_DISCONNECTED = "session_disconnected"
# A damaged balance: a label-first credits claim (`Credits    :`) opened and
# the number did not resolve out of it. Reachable in ordinary operation for
# the same reason as its sector sibling -- a render taken mid-paint.
REASON_DAMAGED_CREDITS_LABEL = "damaged_credits_label"
# A damaged turn count: a label-first claim (`Turns left  :`) opened and the
# number did not resolve out of it. Same mid-paint reachability as its two
# siblings, and the same consequence -- `unreadable` is a NON-write, so a
# half-painted ship-info screen ages the sticky value instead of replacing
# it with a guess.
REASON_DAMAGED_TURNS_LABEL = "damaged_turns_label"
REASONS = frozenset({
    REASON_DAMAGED_COMMAND_PROMPT,
    REASON_DAMAGED_CREDITS_LABEL,
    REASON_DAMAGED_TURNS_LABEL,
    REASON_NOT_TEXT,
    REASON_SESSION_DISCONNECTED,
})

# What the RUNTIME (as opposed to one screen) can say about the balance.
# Two, not three: a sticky store either holds a reading or it does not, and
# there is no third "the store was damaged" state a `CreditsSnapshot` could
# honestly report about itself. A port that answers with something that is
# not a `CreditsSnapshot` at all is an ADAPTER fault and is named by the
# player's own halt vocabulary, not by an outcome invented here.
SNAPSHOT_OUTCOMES = frozenset({OUTCOME_READ, OUTCOME_ABSENT})


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectorRead:
    """What a screen was able to say about where the ship is.

    Frozen, because a verdict that can be rewritten between reading it and
    acting on it is not a verdict.

    The field pairing is enforced in ``__post_init__``, and that enforcement
    is the point of the class: ``sector`` is an ``int`` on the ``read``
    outcome and ``None`` on both others, ``source`` accompanies exactly a
    read, ``reason`` accompanies exactly an unreadable. A caller therefore
    cannot obtain a number without having passed through the outcome, and
    an implementation cannot accidentally ship a number alongside a verdict
    that did not establish one.

    Note what is deliberately NOT here: no ``__bool__``, no ``ok``, no
    ``or``-friendly default. ``SectorRead`` has no truthiness shortcut that
    could quietly fold two outcomes into one at a call site.
    """

    outcome: str
    sector: Optional[int] = None
    source: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome {self.outcome!r} is not one of {sorted(OUTCOMES)}")
        read = self.outcome == OUTCOME_READ
        if read != (self.sector is not None):
            raise ValueError(
                "a sector number accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with sector={self.sector!r}"
            )
        if read != (self.source is not None):
            raise ValueError(
                "a source accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with source={self.source!r}"
            )
        if (self.outcome == OUTCOME_UNREADABLE) != (self.reason is not None):
            raise ValueError(
                "a reason accompanies exactly the 'unreadable' outcome -- "
                f"got outcome={self.outcome!r} with reason={self.reason!r}"
            )
        # `isinstance(True, int)` holds in Python, so an unguarded int check
        # would let `sector=True` through as sector 1 -- the same trap
        # `loops.loader._validate_anchor` and `loops.store._finite_number`
        # both document on the other half of this comparison.
        if self.sector is not None and (
            isinstance(self.sector, bool) or not isinstance(self.sector, int)
        ):
            raise ValueError(f"sector must be an int, got {type(self.sector).__name__}")
        if self.source is not None and self.source not in SOURCES:
            raise ValueError(f"source {self.source!r} is not one of {sorted(SOURCES)}")
        if self.reason is not None and self.reason not in REASONS:
            raise ValueError(f"reason {self.reason!r} is not one of {sorted(REASONS)}")


def sector_unreadable(reason: str) -> SectorRead:
    """The ``unreadable`` verdict, for a caller that establishes the failure
    outside this module -- today only ``protocol._state_response``'s
    dead-socket check, which is a fact about the SESSION rather than about
    the text and so cannot be seen from here.

    Exists so that path constructs its verdict through the same validated
    type as every other, instead of hand-rolling a dict that would drift.
    """
    return SectorRead(outcome=OUTCOME_UNREADABLE, reason=reason)


# ---------------------------------------------------------------------------
# The one source
# ---------------------------------------------------------------------------
#
# ONE prefix, two patterns built from it. `_OPEN_RE` is "a sector bracket was
# opened"; `_VALUE_RE` is that same prefix plus a resolved number and its
# closing bracket. They are composed from `_BRACKET_PREFIX` rather than
# written twice precisely so "opened" and "resolved" can never drift into
# describing different shapes -- if they could, the damaged-anchor branch
# would start firing on prompts that are perfectly fine, or (worse) stop
# firing on ones that are not.
#
# `[ \t]` throughout, never `\s`: `\s` crosses newlines, and the archive
# caught that live on this file's sibling field -- a `\s+` in
# `_TURNS_LEFT_PLAIN_RE` "crossed newlines and forged turns_left from the
# prior line's sector id". Here the input is a single line by contract, so
# this is belt-and-braces against a caller passing a joined block.
#
# `[^\]]*` for the TL= body deliberately swallows both known shapes -- this
# server's `TL=00:00:00` countdown and the classic `TL=00753:0/0/0/850` turn
# count -- because nothing here needs to interpret TL=; it only needs to walk
# past it to the bracket that follows. Interpreting TL= is where the archive
# put a real defect (matching the HH:MM:SS countdown as a turn count and
# silently reporting `turns_left=0`), and this module declines to inherit it.
_BRACKET_PREFIX = r"command[ \t]*\[[ \t]*tl[ \t]*=[^\]]*\][ \t]*:[ \t]*\["
_OPEN_RE = re.compile(_BRACKET_PREFIX, re.I)
_VALUE_RE = re.compile(_BRACKET_PREFIX + r"[ \t]*(\d+)[ \t]*\]", re.I)


def read_current_sector(prompt_line) -> SectorRead:
    """Where the ship is, per this screen's own current prompt line.

    ``prompt_line`` is the settled screen's last non-blank row, stripped --
    ``rows[-1].strip()``, the same line ``classify.classify_screen`` scopes
    its gate anchors to and ``Session.current_prompt_line()`` returns. The
    signature takes ONLY that line, and takes it as text rather than as a
    session, so the function is structurally incapable of being fooled by
    stale body content: it never sees the grid.

    Returns a :class:`SectorRead`, always -- it does not raise, because
    ``absent`` is the ordinary answer for every login, menu and report
    screen and an exception per poll would train a caller to swallow it,
    which is the collapse wearing different clothes.

    **Settling is the caller's job, not this function's.** Canon is explicit
    that screen understanding "operates only on a settled screen... An
    unsettled or mid-arrival screen is not classified". This function
    honours that boundary in the only way it can from here: it never resolves
    a number out of a half-painted bracket, reporting
    ``unreadable/damaged_command_prompt`` instead. It cannot detect a
    mid-arrival prompt that happens to be intact, and does not pretend to.
    """
    if not isinstance(prompt_line, str):
        return SectorRead(outcome=OUTCOME_UNREADABLE, reason=REASON_NOT_TEXT)

    # LAST match, per canon's hard rule. A prompt line normally carries one
    # bracket; two means an echo or an in-band fragment shares the row, and
    # the bottom-most/right-most is the one the server most recently printed.
    values = list(_VALUE_RE.finditer(prompt_line))
    opens = list(_OPEN_RE.finditer(prompt_line))

    if not opens:
        # No sector bracket was even opened. The screen was read in full and
        # makes no claim -- including the CLASSIC-shape command prompt, which
        # genuinely does not carry one (see the module docstring).
        return SectorRead(outcome=OUTCOME_ABSENT)

    # Last-match applied to the damage check too, not only to the value: a
    # resolved bracket EARLIER on the line does not rehabilitate a damaged one
    # after it, because the later one is the more recently printed. Reading
    # the earlier number here would be first-match-wins by the back door.
    if not values or opens[-1].start() > values[-1].start():
        return SectorRead(
            outcome=OUTCOME_UNREADABLE, reason=REASON_DAMAGED_COMMAND_PROMPT
        )

    return SectorRead(
        outcome=OUTCOME_READ,
        sector=int(values[-1].group(1)),
        source=SOURCE_COMMAND_PROMPT,
    )


# ---------------------------------------------------------------------------
# The credits balance (X5) -- what ONE screen said
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreditsRead:
    """What a screen was able to say about the pilot's balance.

    The same three outcomes, the same ``__post_init__`` enforcement, and the
    same deliberate omissions as :class:`SectorRead` -- no ``__bool__``, no
    ``ok``, no ``or``-friendly default -- for the same reason: a caller must
    pass through the outcome to obtain a number, so "we could not read the
    balance" has no expression that quietly folds into "the balance is
    fine". On a stop-loss that fold IS the defeat.
    """

    outcome: str
    balance: Optional[int] = None
    source: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome {self.outcome!r} is not one of {sorted(OUTCOMES)}")
        read = self.outcome == OUTCOME_READ
        if read != (self.balance is not None):
            raise ValueError(
                "a balance accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with balance={self.balance!r}"
            )
        if read != (self.source is not None):
            raise ValueError(
                "a source accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with source={self.source!r}"
            )
        if (self.outcome == OUTCOME_UNREADABLE) != (self.reason is not None):
            raise ValueError(
                "a reason accompanies exactly the 'unreadable' outcome -- "
                f"got outcome={self.outcome!r} with reason={self.reason!r}"
            )
        # `isinstance(True, int)` holds, so an unguarded int check would let
        # `balance=True` through as one credit -- the trap `SectorRead`,
        # `loops.loader._validate_anchor` and `loops.store._finite_number`
        # all document on their own halves of a comparison.
        if self.balance is not None and (
            isinstance(self.balance, bool) or not isinstance(self.balance, int)
        ):
            raise ValueError(f"balance must be an int, got {type(self.balance).__name__}")
        if self.source is not None and self.source not in SOURCES:
            raise ValueError(f"source {self.source!r} is not one of {sorted(SOURCES)}")
        if self.reason is not None and self.reason not in REASONS:
            raise ValueError(f"reason {self.reason!r} is not one of {sorted(REASONS)}")


# ONE label prefix, two patterns built from it -- the `_BRACKET_PREFIX`
# discipline the sector half of this module uses, and for the same reason:
# "opened" and "resolved" cannot drift into describing different shapes if
# neither is written twice.
#
# The `You have N credits` shape gets no OPEN pattern at all. There is no
# prefix of it that unambiguously promises a balance (`You have 3 fighters`
# opens identically), so inventing one would report `unreadable` on ordinary
# screens. The docstring states that narrowing; the consequence is only ever
# a non-write, never a wrong number.
_CREDITS_LABEL_PREFIX = r"credits?[ \t]*[:=]"
_CREDITS_LABEL_OPEN_RE = re.compile(_CREDITS_LABEL_PREFIX, re.I)
_CREDITS_LABEL_VALUE_RE = re.compile(_CREDITS_LABEL_PREFIX + r"[ \t]*(\d[\d,]*)", re.I)
_YOU_HAVE_CREDITS_RE = re.compile(r"you[ \t]+have[ \t]+(\d[\d,]*)[ \t]+credits?\b", re.I)


def read_credits_balance(rendered_text) -> CreditsRead:
    """The pilot's balance, per this screen, from a STRICT source only.

    ``rendered_text`` is a whole settled screen (``Session.render_text()``),
    not a single line: unlike the sector bracket, a balance is a body
    statement and there is no prompt-line scoping available to narrow it.
    That is the honest reason this function is more exposed to the
    forged-balance residual than its sector sibling, and the docstring says
    so rather than implying parity.

    Returns a :class:`CreditsRead`, always -- it does not raise, because
    ``absent`` is the ordinary answer for nearly every screen in the game
    and an exception per render would train a caller to swallow it.

    Settling is the caller's job, exactly as it is for
    :func:`read_current_sector`.
    """
    if not isinstance(rendered_text, str):
        return CreditsRead(outcome=OUTCOME_UNREADABLE, reason=REASON_NOT_TEXT)

    # Position-sorted across BOTH patterns -- see the module docstring for
    # why a per-pattern priority order is not last-match.
    found = [
        (m.end(), m.group(1), SOURCE_YOU_HAVE_CREDITS)
        for m in _YOU_HAVE_CREDITS_RE.finditer(rendered_text)
    ]
    found += [
        (m.end(), m.group(1), SOURCE_CREDITS_LABEL)
        for m in _CREDITS_LABEL_VALUE_RE.finditer(rendered_text)
    ]
    opens = [m.end() for m in _CREDITS_LABEL_OPEN_RE.finditer(rendered_text)]

    if not found:
        # A label opened with nothing resolved anywhere is a damaged claim;
        # no label at all is a screen that simply says nothing about money.
        if opens:
            return CreditsRead(
                outcome=OUTCOME_UNREADABLE, reason=REASON_DAMAGED_CREDITS_LABEL
            )
        return CreditsRead(outcome=OUTCOME_ABSENT)

    found.sort(key=lambda item: item[0])
    last_end, raw, source = found[-1]
    if opens and max(opens) > last_end:
        # Last-match applied to the DAMAGE check too, not only to the value:
        # a resolved balance earlier on the grid does not rehabilitate a
        # damaged claim printed after it. Reading the earlier number here
        # would be first-match-wins by the back door -- and on this field it
        # would hand the floor a balance from before the spend.
        return CreditsRead(
            outcome=OUTCOME_UNREADABLE, reason=REASON_DAMAGED_CREDITS_LABEL
        )

    return CreditsRead(
        outcome=OUTCOME_READ,
        balance=int(raw.replace(",", "")),
        source=source,
    )


# ---------------------------------------------------------------------------
# The credits balance (X5) -- what the RUNTIME knows right now
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreditsSnapshot:
    """The last balance this session observed, and how old it is.

    Produced by :meth:`Session.credits_snapshot`, consumed by the player's
    floor check. Two fields travel together and are validated together
    because reading them apart is the documented defeat: the archive's own
    fix note records a concurrent poll landing between the two assignments
    and pairing "an OLD balance alongside the NEW ts, understating the
    reported age -- ... where a falsely-fresh stale balance is a real
    over-spend defeat."

    ``age_s`` is a *seconds* duration rather than a timestamp on purpose.
    A timestamp would have to be compared against a clock, and the consumer
    (a pure decision function in ``loops/player.py``) has no clock and must
    not acquire one -- two clocks either side of this value is exactly how a
    freshness check silently stops being one.

    ``absent`` means nothing has EVER been observed. It is a genuine
    negative about the observation history, never a claim that the balance
    is zero, and the floor treats it as ``credits_unknown``.

    No ``__bool__``, no ``ok`` -- same omission as its two siblings.
    """

    outcome: str
    balance: Optional[int] = None
    age_s: Optional[float] = None

    def __post_init__(self) -> None:
        if self.outcome not in SNAPSHOT_OUTCOMES:
            raise ValueError(
                f"outcome {self.outcome!r} is not one of {sorted(SNAPSHOT_OUTCOMES)}"
            )
        read = self.outcome == OUTCOME_READ
        if read != (self.balance is not None):
            raise ValueError(
                "a balance accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with balance={self.balance!r}"
            )
        if read != (self.age_s is not None):
            raise ValueError(
                "an age accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with age_s={self.age_s!r}"
            )
        if self.balance is not None and (
            isinstance(self.balance, bool) or not isinstance(self.balance, int)
        ):
            raise ValueError(f"balance must be an int, got {type(self.balance).__name__}")
        if self.age_s is not None:
            # NaN is the danger here, not a type error. `nan > stale` is
            # False, so an un-guarded staleness ladder reads a NaN age as
            # PERFECTLY FRESH and arms an unbounded floor -- the silent
            # direction. Rejected at construction AND re-checked positively
            # at the decision site, because one of the two is a defence and
            # both together are a property.
            if isinstance(self.age_s, bool) or not isinstance(self.age_s, (int, float)):
                raise ValueError(f"age_s must be a number, got {type(self.age_s).__name__}")
            if not math.isfinite(self.age_s) or self.age_s < 0:
                raise ValueError(f"age_s must be finite and non-negative, got {self.age_s!r}")


def credits_never_observed() -> CreditsSnapshot:
    """The ``absent`` snapshot, constructed through the validated type
    rather than hand-rolled at each of its call sites -- the same reason
    :func:`sector_unreadable` exists."""
    return CreditsSnapshot(outcome=OUTCOME_ABSENT)


# ---------------------------------------------------------------------------
# Turns left -- what ONE screen said (WO-HUD-STATUS-BRIDGE)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnsRead:
    """What a screen was able to say about how many turns remain.

    Same shape and same enforcement as :class:`SectorRead` and
    :class:`CreditsRead` -- a number accompanies exactly ``read``, a source
    accompanies exactly ``read``, a reason accompanies exactly
    ``unreadable``. No ``__bool__``, no ``ok``.

    There is deliberately no fourth outcome distinguishing "this screen
    printed a COUNTDOWN clock where a turn count would go" from "this screen
    said nothing about turns". Both are ``absent``, because both mean the
    same thing to every consumer: no number was established here. Inventing
    a reason for the first would require loosening the type's
    ``reason``-implies-``unreadable`` rule, and it would buy nothing -- the
    HUD paints an unknown cell either way.
    """

    outcome: str
    turns: Optional[int] = None
    source: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome {self.outcome!r} is not one of {sorted(OUTCOMES)}")
        read = self.outcome == OUTCOME_READ
        if read != (self.turns is not None):
            raise ValueError(
                "a turn count accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with turns={self.turns!r}"
            )
        if read != (self.source is not None):
            raise ValueError(
                "a source accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with source={self.source!r}"
            )
        if (self.outcome == OUTCOME_UNREADABLE) != (self.reason is not None):
            raise ValueError(
                "a reason accompanies exactly the 'unreadable' outcome -- "
                f"got outcome={self.outcome!r} with reason={self.reason!r}"
            )
        # `isinstance(True, int)` holds, so an unguarded check would let
        # `turns=True` through as one turn -- the trap every sibling on this
        # module documents on its own half of the comparison.
        if self.turns is not None and (
            isinstance(self.turns, bool) or not isinstance(self.turns, int)
        ):
            raise ValueError(f"turns must be an int, got {type(self.turns).__name__}")
        if self.source is not None and self.source not in SOURCES:
            raise ValueError(f"source {self.source!r} is not one of {sorted(SOURCES)}")
        if self.reason is not None and self.reason not in REASONS:
            raise ValueError(f"reason {self.reason!r} is not one of {sorted(REASONS)}")


def turns_unreadable(reason: str) -> TurnsRead:
    """The ``unreadable`` verdict, minted through the validated type -- the
    same reason :func:`sector_unreadable` exists."""
    return TurnsRead(outcome=OUTCOME_UNREADABLE, reason=reason)


# The `TL=` bracket, read for its BODY rather than walked past. This is the
# first interpreter of that field in the reborn tree, and the module's
# sector half (see `_BRACKET_PREFIX` above) declines to be one on purpose:
# "Interpreting TL= is where the archive put a real defect (matching the
# HH:MM:SS countdown as a turn count and silently reporting `turns_left=0`)".
# That defect is closed HERE, by checking the countdown shape FIRST and
# answering `absent` to it, so the only way to reach a number is to have
# already failed to look like a clock.
#
# `[^\]\r\n]*` rather than the sector half's `[^\]]*`: that one is scoped to
# a single line by its caller's contract, and this one is called with the
# same line but is also the function a future caller is most likely to hand
# a block to by mistake. Excluding the newline makes "cannot cross a line"
# a property of the pattern instead of a property of the call site.
_TL_PREFIX = r"\[[ \t]*tl[ \t]*="
_TL_OPEN_RE = re.compile(_TL_PREFIX, re.I)
_TL_BODY_RE = re.compile(_TL_PREFIX + r"([^\]\r\n]*)\]", re.I)
# The CLASSIC-server turn count, enumerated as an ACCEPT-list and anchored at
# both ends: a leading digit run, optionally followed by one `:` and a
# slash-separated stat group ("00753:0/0/0/850", "1000", "0").
#
# **Written as "what a count looks like", never as "what a clock looks
# like".** The obvious implementation is the other way round -- refuse
# `\d{1,2}:\d{2}:\d{2}`, then take whatever digits lead the rest -- and it
# has a hole this one does not: a body that is clock-SHAPED but not exactly
# HH:MM:SS (`1:2:3`, a truncated or differently-padded countdown) escapes
# the refusal and is then read as its leading digits, which for a clock is a
# small number and for `00:...` is the forged `0` this whole field exists to
# make unreachable. Refusing a named hazard only closes the spellings of it
# you thought of; accepting a named shape closes everything else by default.
#
# The countdown is therefore not mentioned in a pattern at all -- it is
# refused because `:00:00` is not a slash-separated stat group, the same way
# every other unrecognised body is refused. There is deliberately no second
# clock-detecting check sitting in front of this one: it could not change an
# outcome, and a guard that cannot change an outcome reads as protection
# while providing none.
#
# The stat group must contain at least one `/`. Allowing a bare `:\d+` tail
# re-opens the hole one notch further down: `TL=00:00` (a truncated or
# half-painted clock) then parses as "count 00, stat group 00" and forges
# the zero again. A slash is what makes a stat group a stat group, and
# requiring it is what keeps `HH:MM` on the refused side. A hypothetical
# classic server printing a single slash-less stat would read as `absent`
# here -- the fail-closed direction, and the one this field must err in.
_TL_TURN_COUNT_RE = re.compile(r"^[ \t]*(\d+)(?::\d+(?:/\d+)+)?[ \t]*$")


def read_turns_left(prompt_line) -> TurnsRead:
    """The turn count this screen's own prompt line states, if it states one.

    ``prompt_line`` is the settled screen's last non-blank row, stripped --
    the same input :func:`read_current_sector` takes, scoped the same way and
    for the same reason: taking the line rather than the session makes the
    function structurally incapable of being fooled by stale body content.

    **The countdown is refused, never coerced.** Two servers spell this field
    differently and only one of them means turns by it:

    - ``TL=00753:0/0/0/850`` -- the CLASSIC-shape TWGS prompt, a turn count.
    - ``TL=00:00:00`` -- this live server's MBBS Gold build, a session
      countdown clock, which is **not** a turn count.

    Reading the second as an integer yields ``0``, and a ``0`` here is not a
    harmless wrong number: it is the reading that says "you are out of
    turns". The archive shipped exactly that and "silently reported
    ``turns_left=0``". This function answers ``absent`` to the clock shape,
    so a forged zero is unreachable rather than merely unlikely.

    **What this means on the live server.** That server uses the bracketed
    countdown form, so this function answers ``absent`` on every one of its
    prompts. That is correct, and it is also why it is not the only producer:
    :func:`read_turns_left_from_screen` reads the body statements this server
    *does* print. Neither function is a fallback for the other's bugs -- they
    read different lines, and the caller's precedence is a policy decision
    that lives with the sticky store, not here.

    Returns a :class:`TurnsRead`, always -- ``absent`` is the ordinary answer
    for most screens and an exception per poll would train a caller to
    swallow it.
    """
    if not isinstance(prompt_line, str):
        return turns_unreadable(REASON_NOT_TEXT)

    # LAST match, per canon's hard rule and exactly as the sector sibling
    # applies it: two brackets on one row means an echo or an in-band
    # fragment shares it, and the bottom-most is the most recently printed.
    bodies = list(_TL_BODY_RE.finditer(prompt_line))
    opens = list(_TL_OPEN_RE.finditer(prompt_line))

    if not opens:
        return TurnsRead(outcome=OUTCOME_ABSENT)

    # Last-match applied to the DAMAGE check too, not only to the value -- a
    # resolved bracket earlier on the line does not rehabilitate a damaged
    # one after it. Reading the earlier body would be first-match-wins by
    # the back door, and on this field it would hand the HUD a count from
    # before the spend.
    if not bodies or opens[-1].start() > bodies[-1].start():
        return turns_unreadable(REASON_DAMAGED_COMMAND_PROMPT)

    counted = _TL_TURN_COUNT_RE.match(bodies[-1].group(1))
    if not counted:
        # Not a count: the HH:MM:SS countdown, any other clock-shaped body,
        # and any spelling nobody here has seen all land together. This is
        # the closed side of the enumeration, and it answers `absent` rather
        # than reaching for whatever digits it can find -- which is the
        # single behaviour that makes a forged `turns_left=0` unreachable.
        return TurnsRead(outcome=OUTCOME_ABSENT)
    return TurnsRead(
        outcome=OUTCOME_READ,
        turns=int(counted.group(1)),
        source=SOURCE_TURN_COUNT_PROMPT,
    )


# ONE label prefix, two patterns built from it -- the `_BRACKET_PREFIX` /
# `_CREDITS_LABEL_PREFIX` discipline, for the third time and the same
# reason: "opened" and "resolved" cannot drift into describing different
# shapes if neither is written twice.
#
# `[ \t]` throughout, never `\s`. This is not a general precaution on this
# field -- it is THE scar. The archive's own `_TURNS_LEFT_PLAIN_RE` used
# `\s+`, which "crossed newlines and forged turns_left from the prior line's
# sector id" (quoted in this module's sector half, where it is cited as the
# reason that half uses `[ \t]` too). A pattern that cannot match a newline
# cannot cross one, so line-anchoring here is structural rather than a
# discipline a later editor has to remember.
#
# The narrative shape gets no OPEN pattern, for the same reason
# `You have N credits` gets none: no prefix of "29990 turns left"
# unambiguously promises a turn count, so inventing one would report
# `unreadable` on ordinary screens. The cost of that narrowing is only ever
# a non-write, never a wrong number.
_TURNS_LABEL_PREFIX = r"turns?[ \t]+left[ \t]*[:=]"
_TURNS_LABEL_OPEN_RE = re.compile(_TURNS_LABEL_PREFIX, re.I)
_TURNS_LABEL_VALUE_RE = re.compile(_TURNS_LABEL_PREFIX + r"[ \t]*(\d[\d,]*)", re.I)
_TURNS_NARRATIVE_RE = re.compile(r"(\d[\d,]*)[ \t]+turns?[ \t]+left\b", re.I)


def read_turns_left_from_screen(rendered_text) -> TurnsRead:
    """The turn count this screen states in its BODY, if it states one.

    ``rendered_text`` is a whole settled screen (``Session.render_text()``),
    not a single line -- like the credits balance and unlike the sector
    bracket, a turn count is a body statement with no prompt-line scoping
    available to narrow it. That is the honest reason this function is more
    exposed to a forged read than :func:`read_turns_left`, and this docstring
    says so rather than implying parity.

    Two accepted shapes, both of which this live server actually prints:

    - ``One turn deducted, 29990 turns left.`` -- the post-move narrative.
    - ``Turns left  : 850`` -- the ship-info (``I``) screen, label-first.

    **Both are line-anchored by construction**, via ``[ \\t]`` in place of
    ``\\s`` throughout. The archive's version of this exact field used
    ``\\s+``, crossed a newline, and forged a turn count out of the previous
    line's sector id. A regex that cannot match a newline cannot repeat that,
    whatever a future caller passes in.

    **What it will not read.** A line must contain the literal token
    ``turns left`` adjacent to the number, so a bare count elsewhere on the
    grid cannot be mistaken for one: the game-select menu's ``Turns:1000``
    column, a fighter count, and a sector id all fail to match rather than
    being filtered out afterwards. Refusal by construction, not by blocklist.

    Returns a :class:`TurnsRead`, always. Settling is the caller's job,
    exactly as it is for the other two readers.
    """
    if not isinstance(rendered_text, str):
        return turns_unreadable(REASON_NOT_TEXT)

    # Position-sorted across BOTH patterns -- a per-pattern priority order
    # would not be last-match, which is the point the credits sibling makes
    # at the same spot.
    found = [
        (m.end(), m.group(1), SOURCE_TURNS_LEFT_NARRATIVE)
        for m in _TURNS_NARRATIVE_RE.finditer(rendered_text)
    ]
    found += [
        (m.end(), m.group(1), SOURCE_TURNS_LEFT_LABEL)
        for m in _TURNS_LABEL_VALUE_RE.finditer(rendered_text)
    ]
    opens = [m.end() for m in _TURNS_LABEL_OPEN_RE.finditer(rendered_text)]

    if not found:
        # A label opened with nothing resolved anywhere is a damaged claim;
        # no label at all is a screen that simply says nothing about turns.
        if opens:
            return turns_unreadable(REASON_DAMAGED_TURNS_LABEL)
        return TurnsRead(outcome=OUTCOME_ABSENT)

    found.sort(key=lambda item: item[0])
    last_end, raw, source = found[-1]
    if opens and max(opens) > last_end:
        # Last-match applied to the damage check as well: a resolved count
        # earlier on the grid does not rehabilitate a damaged claim printed
        # after it.
        return turns_unreadable(REASON_DAMAGED_TURNS_LABEL)

    return TurnsRead(
        outcome=OUTCOME_READ,
        turns=int(raw.replace(",", "")),
        source=source,
    )


# ---------------------------------------------------------------------------
# Turns left -- what the RUNTIME knows right now
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnsSnapshot:
    """The last turn count this session observed, and how old it is.

    Produced by :meth:`Session.turns_snapshot`, consumed by the HUD bridge.
    Same two-fields-travel-together contract as :class:`CreditsSnapshot`, for
    the same documented reason: reading the pair apart is how a concurrent
    poll ends up pairing an old value with a new timestamp.

    ``absent`` means nothing has ever been observed. It is a genuine negative
    about the observation history, never a claim that zero turns remain --
    which on this field is the single most important distinction the type
    carries, and the one the archive lost.
    """

    outcome: str
    turns: Optional[int] = None
    age_s: Optional[float] = None

    def __post_init__(self) -> None:
        if self.outcome not in SNAPSHOT_OUTCOMES:
            raise ValueError(
                f"outcome {self.outcome!r} is not one of {sorted(SNAPSHOT_OUTCOMES)}"
            )
        read = self.outcome == OUTCOME_READ
        if read != (self.turns is not None):
            raise ValueError(
                "a turn count accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with turns={self.turns!r}"
            )
        if read != (self.age_s is not None):
            raise ValueError(
                "an age accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with age_s={self.age_s!r}"
            )
        if self.turns is not None and (
            isinstance(self.turns, bool) or not isinstance(self.turns, int)
        ):
            raise ValueError(f"turns must be an int, got {type(self.turns).__name__}")
        if self.age_s is not None:
            # NaN is the danger, not a type error -- `nan >= stale` is False,
            # so an unguarded freshness ladder reads a NaN age as perfectly
            # fresh. Rejected here AND handled positively by the HUD
            # composer, because one of the two is a defence and both together
            # are a property.
            if isinstance(self.age_s, bool) or not isinstance(self.age_s, (int, float)):
                raise ValueError(f"age_s must be a number, got {type(self.age_s).__name__}")
            if not math.isfinite(self.age_s) or self.age_s < 0:
                raise ValueError(f"age_s must be finite and non-negative, got {self.age_s!r}")


def turns_never_observed() -> TurnsSnapshot:
    """The ``absent`` snapshot, minted through the validated type rather than
    hand-rolled at each call site -- the same reason
    :func:`credits_never_observed` exists."""
    return TurnsSnapshot(outcome=OUTCOME_ABSENT)


# ---------------------------------------------------------------------------
# Sector -- what the RUNTIME last SAW (presentational stickiness)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectorSnapshot:
    """The last sector this session saw stated, and how old that sighting is.

    **This is not** :meth:`Session.last_known_sector`, and the difference is
    the reason it exists. That method answers "may I attribute a per-sector
    FACT right now?" and is epoch-invalidated -- it goes ``None`` the moment
    anything is sent, because a world-model write against a stale sector is
    the live incident it was built to prevent. This type answers a different
    and much weaker question: "what is the last sector the operator was
    shown?" A HUD cell that blanked itself after every keystroke would be
    reporting the *guard's* state, not the ship's.

    Keeping them apart is deliberate. Borrowing the safety-scoped memory for
    a display would either weaken that memory or make the display useless,
    and which of the two happened would depend on whoever edited it next.

    Same two-fields-together contract as its siblings.
    """

    outcome: str
    sector: Optional[int] = None
    age_s: Optional[float] = None

    def __post_init__(self) -> None:
        if self.outcome not in SNAPSHOT_OUTCOMES:
            raise ValueError(
                f"outcome {self.outcome!r} is not one of {sorted(SNAPSHOT_OUTCOMES)}"
            )
        read = self.outcome == OUTCOME_READ
        if read != (self.sector is not None):
            raise ValueError(
                "a sector accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with sector={self.sector!r}"
            )
        if read != (self.age_s is not None):
            raise ValueError(
                "an age accompanies exactly the 'read' outcome -- "
                f"got outcome={self.outcome!r} with age_s={self.age_s!r}"
            )
        if self.sector is not None and (
            isinstance(self.sector, bool) or not isinstance(self.sector, int)
        ):
            raise ValueError(f"sector must be an int, got {type(self.sector).__name__}")
        if self.age_s is not None:
            if isinstance(self.age_s, bool) or not isinstance(self.age_s, (int, float)):
                raise ValueError(f"age_s must be a number, got {type(self.age_s).__name__}")
            if not math.isfinite(self.age_s) or self.age_s < 0:
                raise ValueError(f"age_s must be finite and non-negative, got {self.age_s!r}")


def sector_never_observed() -> SectorSnapshot:
    """The ``absent`` snapshot, minted through the validated type."""
    return SectorSnapshot(outcome=OUTCOME_ABSENT)


# ---------------------------------------------------------------------------
# Warp list on a genuine sector-status line (world-model ingest helper)
# ---------------------------------------------------------------------------

_WARPS_STATUS_LINE_RE = re.compile(
    r"^Warps to Sector\(s\)\s*:?\s*(.*)$",
    re.I | re.M,
)


def read_warps_from_sector_status(rendered_text) -> Optional[list[int]]:
    """Destinations from the LAST ``Warps to Sector(s) :`` status line.

    Returns ``None`` when no such line appears (caller should not write
    warps). Returns ``[]`` when the line is present but empty. Matches
    paren-wrapped and plain ``N - M`` shapes from settled main_command
    screens — last-match over the grid, same discipline as full
    ``parse_state()`` warps extraction.
    """
    if not isinstance(rendered_text, str):
        return None
    matches = list(_WARPS_STATUS_LINE_RE.finditer(rendered_text))
    if not matches:
        return None
    tail = matches[-1].group(1).strip()
    if not tail:
        return []
    return [int(m.group(0)) for m in re.finditer(r"\d+", tail)]


# ---------------------------------------------------------------------------
# Port flyby -- the `Ports :` line of a sector-status block (WO-EXPLORE-
# AUTOMATION-GATE E2)
# ---------------------------------------------------------------------------

_SECTOR_STATUS_LINE_RE = re.compile(r"^[ \t]*Sector[ \t]*:[ \t]*(\d+)", re.I | re.M)
_PORTS_STATUS_LINE_RE = re.compile(r"^[ \t]*Ports?[ \t]*:[ \t]*(.*)$", re.I | re.M)
# `Class 2 (BSB)` -- the parenthesised buy/sell TRIPLE is the posture. Canon
# stores the letters (`"class": "BSB"`), never the digit
# (`canon/engine/world-model.md` §"Examples", `canon/engine/screen-
# understanding.md` §"Examples").
_PORT_CLASS_RE = re.compile(r"\bClass[ \t]+\d+[ \t]*\(([BS]{3})\)", re.I)
# What TW prints for a sector with no port.
_PORTS_NONE_RE = re.compile(r"^(none|<none>|-|—)$", re.I)


@dataclass(frozen=True)
class PortRead:
    """Tri-state outcome of reading a sector-status ``Ports :`` flyby.

    Three states, because two of them are NOT the same and collapsing them
    corrupts the world model in opposite directions:

    * ``observed=False`` — no genuine sector-status block on screen. The
      caller must **omit** the ``port`` key so a previously-learned port is
      preserved (`world_model.write_from_state`: absent fields are preserved).
    * ``observed=True, port=None`` — the block said ``Ports : None``. That is
      a positive statement that this sector has no port, and canon's write
      hook spends an explicit ``None`` to CLEAR a stale record.
    * ``observed=True, port={...}`` — a real port. ``class`` is present only
      when a buy/sell triple was actually read.

    A two-state return (``dict | None``) cannot express this: it would make
    "nothing on screen" indistinguishable from "definitely no port", and the
    write hook would either clear records it never observed or never clear
    ones it did.
    """

    observed: bool
    port: Optional[dict] = None


def _sector_status_block(rendered_text: str) -> Optional[str]:
    """The LAST genuine sector-status block, or ``None``.

    Canon's provenance gate (`canon/engine/screen-understanding.md`
    §"Block-scoped, gated reads for anything persisted"): a ``Sector : N``
    line followed, **before the next blank line**, by a sibling ``Ports :`` /
    ``Warps to Sector(s) :`` marker. It exists "so that narrative text merely
    *reproducing* a status line's shape does not get ingested as real sector
    data" — a game whose flavour text quotes a sector readout would otherwise
    write the world model.

    Last-match over the grid, the same discipline
    ``read_warps_from_sector_status`` and ``parse_state`` already use: on a
    scrolled screen the newest block is the true one.
    """
    best: Optional[str] = None
    for block in re.split(r"\n[ \t]*\n", rendered_text):
        if not _SECTOR_STATUS_LINE_RE.search(block):
            continue
        # The sibling-marker requirement IS the gate.
        if not (
            _PORTS_STATUS_LINE_RE.search(block)
            or _WARPS_STATUS_LINE_RE.search(block)
        ):
            continue
        best = block
    return best


def read_port_from_sector_status(rendered_text) -> PortRead:
    """Read the ``Ports :`` flyby from a settled sector-status screen.

    Turn-free: this is the line a sector display already prints, so a caller
    learns a port's buy/sell posture **without docking, sending, or spending
    a turn** — which is what makes it safe for the explore loop to ingest on
    every hop.

    ``class`` is emitted ONLY for a genuine ``([BS]{3})`` triple. A special
    port (``Class 0 (Special)``) reads as *present but classless* rather than
    inventing ``"Special"`` as a commodity posture: canon's class vocabulary
    is buy/sell letters, and `world_model.write_from_state` omits an absent
    ``class`` so whatever was previously learned (e.g. from a CIM report)
    survives. Never invent a posture the screen did not state.

    Never raises; a non-``str`` reads as unobserved.
    """
    if not isinstance(rendered_text, str):
        return PortRead(observed=False)
    block = _sector_status_block(rendered_text)
    if block is None:
        return PortRead(observed=False)
    matches = list(_PORTS_STATUS_LINE_RE.finditer(block))
    if not matches:
        # A genuine block that simply carries no `Ports :` line (warps-only
        # render) states nothing about a port -- unobserved, not "no port".
        return PortRead(observed=False)
    tail = matches[-1].group(1).strip()
    if not tail or _PORTS_NONE_RE.match(tail):
        return PortRead(observed=True, port=None)
    klass = _PORT_CLASS_RE.search(tail)
    if klass is None:
        return PortRead(observed=True, port={})
    return PortRead(observed=True, port={"class": klass.group(1).upper()})


# ---------------------------------------------------------------------------
# Docked commerce report -- the commodity extraction canon's Ingestion section
# calls "the existing commodity extraction, never a second row parser"
# ---------------------------------------------------------------------------
#
# WO-EXPLORE-DOCK-NEW-PORT. Canon (`/engine/world-model.md` § Ingestion) and
# `world_model.write_port_only`'s own docstring both describe this reader as
# already existing and merely reused. It did not exist: `write_port_only` had
# no product caller at all, and the three symbols its docstring names
# (`protocol._write_world_model`, `state_parser.is_genuine_port_report`,
# `parse_state`) have no definition anywhere in the tree. So the writer was a
# fully-tested consumer of a shape nothing produced. This is that producer --
# THE one, so that canon's "never a second row parser" stays true going
# forward rather than being a rule about a parser that was never written.
#
# The commodity vocabulary is the CLOSED three-name set canon fixes in
# `/strategy/port-economics.md` (first letter = Fuel Ore, second = Organics,
# third = Equipment), not an open `\w+`. That is the provenance gate for this
# screen, and it is the same discipline `_sector_status_block` applies to
# sector reads: narrative text that merely reproduces a table's shape must not
# become persisted world data. A port whose report names something outside the
# closed set is a screen we do not understand, and this reader says so rather
# than ingesting the rows it happened to recognize.
_COMMERCE_REPORT_HEADER_RE = re.compile(r"^Commerce report for .+?:", re.I | re.M)
#: The column header, which every captured report carries directly above the
#: rows. Requiring it (not just the "Commerce report" line) is what keeps a
#: report whose table scrolled off from yielding a confident empty list.
_COMMERCE_COLUMNS_RE = re.compile(
    r"^[ \t]*Items[ \t]+Status[ \t]+Trading[ \t]+%[ \t]+of[ \t]+max", re.I | re.M
)
#: Closed set, ordered as canon orders the class triple.
COMMERCE_COMMODITIES: tuple[str, ...] = ("Fuel Ore", "Organics", "Equipment")
_COMMERCE_ROW_RE = re.compile(
    r"^(?P<name>Fuel Ore|Organics|Equipment)[ \t]+"
    r"(?P<status>Buying|Selling)[ \t]+"
    r"(?P<amount>[\d,]+)[ \t]+"
    r"(?P<pct>\d+)%",
    re.I | re.M,
)


@dataclass(frozen=True)
class PortReportRead:
    """Outcome of reading a docked commerce report.

    Two states only, and deliberately NOT the tri-state `PortRead` uses. A
    commerce report is a screen you reached by spending a turn to dock; it
    never says "this sector has no port" (the sector-status flyby is what
    says that). So there is no third "positively absent" state to express,
    and inventing one would give a caller an explicit `None` to write --
    which under canon's upsert semantics CLEARS the port record wholesale.

    ``observed=False`` means "this is not a commerce report I can vouch for",
    and the only safe response is to write nothing.
    """

    observed: bool
    commodities: tuple[dict, ...] = ()


def read_port_commodities_from_report(rendered_text) -> PortReportRead:
    """Read the commodity table from a settled docked commerce report.

    **Turn-costly, unlike `read_port_from_sector_status`.** That reader parses
    the `Ports :` flyby a sector display prints for free; this one parses the
    screen you only see after `P` -> `T` -> `Docking...`, which the captured
    fixture records as "One turn deducted". Callers must treat reaching this
    screen as a spend, never as a free upgrade of a flyby read.

    Emits canon's exact schema shape (`/engine/world-model.md` § Schema):
    ``{name, status, amount, pct}`` with ``status`` lowercased to canon's
    ``buying``/``selling`` vocabulary.

    **Fails closed as a whole screen, never row-by-row.** A genuine header
    whose rows do not all parse is a report in a layout this reader does not
    know, and a partial commodity list is worse than none: canon's upsert
    replaces the stored list outright ("an old and new `port` commodities list
    are never unioned; the new one wins outright"), so writing two of three
    rows would silently DELETE the third from a previously complete record.

    Never raises; a non-``str`` reads as unobserved.
    """
    if not isinstance(rendered_text, str):
        return PortReportRead(observed=False)
    header = list(_COMMERCE_REPORT_HEADER_RE.finditer(rendered_text))
    if not header:
        return PortReportRead(observed=False)
    # Last-match discipline, as everywhere else in this module: on a scrolled
    # grid the newest report is the true one. Anything above the final header
    # is scrollback from a port we have already left.
    tail = rendered_text[header[-1].start():]
    if not _COMMERCE_COLUMNS_RE.search(tail):
        return PortReportRead(observed=False)
    rows = list(_COMMERCE_ROW_RE.finditer(tail))
    if not rows:
        return PortReportRead(observed=False)
    seen: dict[str, dict] = {}
    for m in rows:
        name = m.group("name")
        # Normalize to canon's spelling rather than the screen's casing.
        for canonical in COMMERCE_COMMODITIES:
            if canonical.lower() == name.lower():
                name = canonical
                break
        seen[name] = {
            "name": name,
            "status": m.group("status").lower(),
            "amount": int(m.group("amount").replace(",", "")),
            "pct": int(m.group("pct")),
        }
    if len(seen) != len(COMMERCE_COMMODITIES):
        # A real report always prints all three rows; the captured fixtures
        # both do. Fewer means the table was clipped by the viewport or the
        # layout is one we have not seen -- either way, not vouchable.
        return PortReportRead(observed=False)
    ordered = tuple(seen[n] for n in COMMERCE_COMMODITIES)
    return PortReportRead(observed=True, commodities=ordered)


# ---------------------------------------------------------------------------
# Serialization -- the one place this verdict becomes wire bytes
# ---------------------------------------------------------------------------


def sector_wire(read: SectorRead) -> dict:
    """The verdict as a JSON-safe object, and the ONLY place it is shaped
    for the wire.

    Bounded by construction: every value is either an ``int`` (the sector)
    or a member of :data:`OUTCOMES` / :data:`SOURCES` / :data:`REASONS`. No
    branch here can emit a slice of the screen, because no string reaches
    this function that did not come from this module's own constants -- which
    is the property canon ``DECISIONS.md`` §C.2 / §C.2.1 asked of every
    structured answer leaving the session, and which ``protocol.py``'s
    ``_status_response`` docstring explicitly names as this WO's job:
    "that number must arrive as a bounded daemon-side derivation (an int on
    ``state``/``status``), never by shipping the raw prompt line for a client
    to re-parse".

    ``sector`` / ``source`` / ``reason`` are OMITTED rather than set to
    ``null`` when they do not apply, so a caller doing ``wire["sector"]``
    raises instead of quietly binding ``None`` -- the same choice
    ``_status_response`` made for ``prompt`` and ``_login_failure_response``
    made for ``screen``. ``outcome`` is always present, so "there is no
    number here" is never expressed by silence.
    """
    wire = {"outcome": read.outcome}
    if read.sector is not None:
        wire["sector"] = read.sector
    if read.source is not None:
        wire["source"] = read.source
    if read.reason is not None:
        wire["reason"] = read.reason
    return wire
