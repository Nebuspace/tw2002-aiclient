"""Read the ship's CURRENT SECTOR off a settled screen -- the precondition
every macro replay re-checks before it presses anything.

WO-P2-G4-X1. Pure and deterministic: this module takes text and returns a
verdict. It holds no session, opens no socket, and cannot send a keystroke
(a test enforces that by AST scan rather than asserting it). Comparing the
answer to a macro's ``start_anchor``, and deciding what to do about the
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

import re
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "OUTCOME_ABSENT",
    "OUTCOME_READ",
    "OUTCOME_UNREADABLE",
    "OUTCOMES",
    "REASON_DAMAGED_COMMAND_PROMPT",
    "REASON_NOT_TEXT",
    "REASON_SESSION_DISCONNECTED",
    "REASONS",
    "SOURCE_COMMAND_PROMPT",
    "SOURCES",
    "SectorRead",
    "read_current_sector",
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
SOURCES = frozenset({SOURCE_COMMAND_PROMPT})

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
REASONS = frozenset({
    REASON_DAMAGED_COMMAND_PROMPT,
    REASON_NOT_TEXT,
    REASON_SESSION_DISCONNECTED,
})


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
