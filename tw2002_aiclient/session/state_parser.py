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
* ``canon/architecture/cli-verbs.md:104``: ``state`` is "parsed structured
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
SOURCES = frozenset({
    SOURCE_COMMAND_PROMPT,
    SOURCE_YOU_HAVE_CREDITS,
    SOURCE_CREDITS_LABEL,
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
REASONS = frozenset({
    REASON_DAMAGED_COMMAND_PROMPT,
    REASON_DAMAGED_CREDITS_LABEL,
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
