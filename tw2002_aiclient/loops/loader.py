"""Load ONE taught macro by name, validated for execution.

WO-P2-G4-X2. Pure filesystem read, like its sibling ``store.py``: this
module opens JSON files and reports what it found. It never writes the
store, never touches the session, and cannot send a keystroke. Recording a
macro (``tw record``) is a writer and does not exist yet; playing one is the
App Autopilot Model's job and is deliberately absent here -- this module
hands a *validated program* to whatever eventually presses it, and nothing
more.

The difference from ``store.read_loop_store`` is the difference between
DISPLAY and EXECUTION, and it is the whole reason this is a separate
surface. The listing answers "what is in the store?" -- one corrupt file
among twenty leaves nineteen rows worth showing, so it reports failure in
band and keeps going. This answers "may the app press THIS macro's keys?",
where there is exactly one document in question and a half-answer is worse
than no answer. So the listing returns a report and this raises.

Canon
-----
* ``canon/engine/macros.md`` §Schema defines the document: ``name`` /
  ``start_anchor`` / ``source`` / ``created_ts`` / ``mined_stats``, and
  ``steps[]`` of ``{input, wait_prompt, expected_post_class}``. Its two
  invariants govern every rule below: (1) the substrate is human-
  demonstrated and human-approved, never AI-generated live; (2) never fire
  an unverified or destructive send.
* ``canon/architecture/cli-verbs.md:36-38`` puts the loop surfaces among the
  **daemon-free reads** -- direct on-disk artifact reads that work with the
  daemon stopped. No protocol verb, no round trip.
* ``canon/engine/candidate-mining.md:31`` / ``world-identity.md:132-134``
  name the on-disk home, and ``macros.md:224-228`` makes approval a matter
  of FILE LOCATION: ``state/skills/<name>.json`` is blessed,
  ``state/skills/_drafts/<name>.json`` is an inert proposal. Drafts are
  therefore opt-in here, exactly as they are in the listing.
* The flat-vs-per-world path divergence is recorded in ``store.py``'s
  docstring and is unchanged by this module -- it reads through the same
  ``loops_dir`` / ``drafts_dir`` seam, so the migration stays a path change
  in one place.

Three outcomes, never two
-------------------------
"there is no loop called X", "I could not finish looking for X", and "X is
not a playable macro" are three different facts, and an operator (or a
player deciding whether to press keys) can act on only one of them. They get
three exception types and they never render alike:

* ``LoopNotFound``   -- every consulted root was read, every candidate
  document was identified, and none carried the name. The ONLY outcome
  entitled to say the loop does not exist.
* ``LoopUnreadable`` -- a root or a candidate could not be read, so the
  search never completed. Nothing about existence was established.
* ``LoopMalformed``  -- the loop was found and read, and it is not something
  that may be pressed into a live game.
* ``LoopAmbiguous``  -- more than one document claims the name. Which
  keystrokes the human meant is unknown, and guessing is not answering.

Collapsing the second into the first is the defect this repo has now fixed
four times (``credentials`` / ``env.load_dotenv`` / ``get_password`` /
``daemon_alive``), and ``Path.exists()`` is its usual vehicle -- it answers
False for a file that is demonstrably present under an unreadable directory
(measured in ``909ab01``). There is no ``exists()`` in this module; it opens
and classifies, and a test pins that.

The name-keyed lookup has a door onto the same collapse that a directory
listing does not: **a candidate we could not identify might have been the
one asked for.** So an unreadable sibling poisons a MISS -- and only a miss.
Once the loop is found the answer is established, and a corrupt neighbour
cannot unestablish it; a loader that failed on any unreadable file would be
unusable in a store with one damaged document.

Identity is the document's ``name``, never the filename
-------------------------------------------------------
Resolving ``skills/<name>.json`` would be both faster and wrong. The writer
sanitizes names into stems, so a stem is a lossy derivation -- measured
against the 19 real archived artifacts, 3 of them have a stem that differs
from the document's own ``name`` (a dropped trailing underscore, e.g. stem
``mined-1-_NUM___NUM`` for name ``mined-1-_NUM___NUM_``). A path-guessing
loader misses those three outright and reports a stem as an identity for the
other sixteen. So the roots are scanned and matched on the ``name`` the
document actually carries.

Strictness: fail-closed on the steps
------------------------------------
One bad step rejects the whole loop. A macro is an ORDERED keystroke
sequence -- dropping the bad one and playing the rest does not degrade it,
it produces a different macro nobody taught, whose remaining keystrokes land
on screens the recording never saw. That is precisely the blind pump
``macros.md`` invariant 2 exists to make impossible, and a partially-valid
macro is more dangerous than an invalid one because it looks playable.
Truncating at the first bad step is rejected for the same reason plus one
more: a macro's steps are a transaction in a live economy, and a pair-trade
whose buy half executes and whose sell half is dropped leaves the ship
holding cargo, reported as a successful partial run. Halting mid-run on a
live surprise (which canon requires) is not a licence to *plan* an
incomplete run before the first send.

Refusing is not the same as being unhelpful, so the refusal carries EVERY
defect found -- an operator fixing the JSON sees all of them in one pass
rather than rediscovering them one run at a time.

Two kinds of field, two treatments, and the line is deliberate:

* fields the player must **act on** are fail-closed. ``start_anchor`` is a
  safety precondition, so an uncheckable one is refused rather than quietly
  downgraded to "absent" -- canon gives an ABSENT anchor an explicit force
  path, and a damaged anchor must not inherit it.
* fields that are only **displayed** degrade to unknown rather than blocking
  a playable macro. ``source`` is never defaulted to ``recorded`` -- the
  strongest claim the schema makes -- which is the same call the listing
  already made.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

# The shared document-admission gate, imported rather than re-implemented so
# the bar for "this is a macro at all" cannot drift between what `tw loops`
# lists and what a player is allowed to load. Importing a sibling's private
# name is the disclosed cost of not forking the gate -- the same call
# `env.py` made for `credentials._decoder_detail`, and drift in a duplicated
# gate is exactly how the collapse this module exists to prevent survived in
# four places at once. A test pins the coupling so a rename fails fast.
from .store import (
    CAUSE_CORRUPT,
    CAUSE_DENIED,
    CAUSE_MALFORMED,
    CAUSE_UNUSABLE,
    DRAFTS_DIRNAME,
    SOURCE_VALUES,
    _read_document,
    drafts_dir,
    loops_dir,
)

__all__ = [
    "CAUSE_CORRUPT",
    "CAUSE_DENIED",
    "CAUSE_MALFORMED",
    "CAUSE_UNUSABLE",
    "Loop",
    "LoopAmbiguous",
    "LoopLoadError",
    "LoopMalformed",
    "LoopNotFound",
    "LoopStep",
    "LoopUnreadable",
    "ReadFailure",
    "StepDefect",
    "load_loop",
]


# ---------------------------------------------------------------------------
# What a caller gets back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoopStep:
    """One validated step: what to press, what to confirm, what to expect.

    Field names are canon's own (``macros.md`` §Schema), untranslated -- a
    rename here would be a second dialect for the same three ideas, and the
    JSON on disk would stop matching the structure in memory.
    """

    input: str
    wait_prompt: Optional[str]
    expected_post_class: str


@dataclass(frozen=True)
class Loop:
    """A macro validated for execution.

    Frozen, and ``steps`` is a TUPLE rather than a list: ``frozen=True`` does
    not deep-freeze a mutable field, and validation is worthless if the thing
    validated can be rewritten between loading and pressing.

    ``start_anchor`` is ``None`` for a legacy macro recorded before anchor
    tracking existed -- 17 of the 19 real archived documents carry no anchor
    at all. That is a legal document, NOT a defect, and canon owns what a
    player must do about it: refuse to replay by default, past which only an
    explicit human force may go. This module never invents one.

    ``source`` is ``None`` unless the document carried one of canon's two
    values; ``draft`` is the real approval gate, since approval is expressed
    by file location.
    """

    name: str
    steps: tuple[LoopStep, ...]
    start_anchor: Optional[int]
    source: Optional[str]
    created_ts: Optional[str]
    draft: bool
    path: str


@dataclass(frozen=True)
class ReadFailure:
    """One thing that could not be read, and why. ``path`` may be a file or
    a directory -- both block a search the same way."""

    path: str
    cause: str
    reason: str


@dataclass(frozen=True)
class StepDefect:
    """One reason a step may not be pressed: which step, which field, why."""

    index: int
    field: str
    reason: str


# ---------------------------------------------------------------------------
# The three (four) outcomes
# ---------------------------------------------------------------------------


class LoopLoadError(Exception):
    """Base for every way ``load_loop`` can decline to return a macro.

    A common base so a caller may catch the family in one place (a CLI verb
    printing an error), while the SUBCLASSES stay distinct so a caller that
    must branch -- a player deciding whether to press keys -- can never
    silently treat one outcome as another. None of them inherits from any
    other: that is what makes "absent" and "could not tell" structurally
    unconfusable rather than conventionally so.
    """


class LoopNotFound(LoopLoadError):
    """No document in the consulted roots carries this name, and the search
    was COMPLETE -- every root was listed and every candidate identified.

    The only outcome entitled to assert the negative. ``searched`` names the
    roots actually consulted, because a miss is a claim about where we
    looked: saying "no such loop" after checking one of two places would
    over-claim, and drafts are not consulted unless asked for.
    """

    def __init__(self, name: str, searched) -> None:
        self.name = name
        self.searched = tuple(str(root) for root in searched)
        where = ", ".join(self.searched) or "nowhere -- no store directory was consulted"
        super().__init__(f"no loop named {name!r} in {where}")


class LoopUnreadable(LoopLoadError):
    """The search could not be completed, so nothing about the loop's
    existence was established -- it may be sitting in the file we could not
    open.

    Raised ONLY when the loop was not found, never when it was: an unread
    neighbour cannot unestablish an answer already in hand.

    ``blockers`` names every obstacle with its own ``cause`` and ``reason``,
    because an operator can only fix a file they can find, and "fix
    permissions" / "replace a wrong path" / "repair a damaged document" are
    three different jobs.
    """

    def __init__(self, name: str, blockers) -> None:
        self.name = name
        self.blockers = tuple(blockers)
        detail = "; ".join(f"{b.path}: {b.reason}" for b in self.blockers)
        super().__init__(
            f"could not establish whether a loop named {name!r} exists -- "
            f"{len(self.blockers)} unreadable: {detail}"
        )


class LoopMalformed(LoopLoadError):
    """The loop was found and read, and it is not a macro that may be
    pressed into a live game.

    Deliberately carries no partial program: there is no attribute here from
    which a caller could recover "the good steps", because an ordered
    sequence minus a step is a different macro nobody taught. ``defects``
    is diagnostics for the human repairing the JSON -- every problem found,
    not just the first -- and is empty for a whole-document refusal (an
    uncheckable anchor, or no steps at all), where ``reason`` carries it.
    """

    def __init__(self, name: str, path, reason: str, defects=()) -> None:
        self.name = name
        self.path = str(path)
        self.cause = CAUSE_MALFORMED
        self.reason = reason
        self.defects = tuple(defects)
        detail = f"{reason} ({self.path})"
        if self.defects:
            detail += "\n" + "\n".join(
                f"  step {d.index}: {d.field} -- {d.reason}" for d in self.defects
            )
        super().__init__(f"loop {name!r} is not playable: {detail}")


class LoopAmbiguous(LoopLoadError):
    """More than one document in the same root claims this name.

    Reachable by hand-edit, which canon explicitly expects operators to do
    (``macros.md``: numeric generalization "currently requires a human to
    hand-edit the macro JSON"). Resolving it by sort order would invent an
    answer about which keystrokes to press, on an artifact that spends
    credits -- so this refuses and names both files.
    """

    def __init__(self, name: str, paths) -> None:
        self.name = name
        self.paths = tuple(str(p) for p in paths)
        super().__init__(
            f"{len(self.paths)} documents claim the name {name!r}, "
            f"and only a human can say which was meant: {', '.join(self.paths)}"
        )


# ---------------------------------------------------------------------------
# Step validation
# ---------------------------------------------------------------------------


def _validate_step(index: int, raw: Any) -> tuple[Optional[LoopStep], list[StepDefect]]:
    """One step, validated against ``macros.md`` §Schema.

    Returns the step and an EMPTY defect list, or ``None`` and every defect
    found in it. Validation does not short-circuit within a step for the same
    reason the loop does not short-circuit across steps: the caller is a
    human about to edit JSON.
    """
    defects: list[StepDefect] = []
    if not isinstance(raw, Mapping):
        return None, [
            StepDefect(index, "step", f"is a {type(raw).__name__}, expected an object")
        ]

    # `input` -- "the keystroke(s) to send". `""` is canon's bare
    # Enter/accept-default and is 61 of the real store's 245 steps, so a
    # truthiness check here would reject a quarter of the real corpus. A
    # non-str would be stringified somewhere downstream and pressed as
    # whatever `str()` produced -- `True` sends "True". Note `bool` is an
    # `int` in Python but not a `str`, so it is already caught.
    keystrokes = raw.get("input")
    if not isinstance(keystrokes, str):
        kind = "is absent" if "input" not in raw else f"is a {type(keystrokes).__name__}"
        defects.append(StepDefect(index, "input", f"{kind}, expected the keystrokes to send"))

    # `wait_prompt` -- optional. Absent and explicit null are the same fact
    # (206 of 245 real steps have none). When present it is compiled with
    # exactly the call `settle` will make -- `re.compile(pattern)`, no flags,
    # because wait_prompt regexes are CASE-SENSITIVE by hard rule -- so a
    # pattern that loads here is one the send path can compile.
    #
    # Compileability is checkable; correctness is not. `Command [TL=` is a
    # perfectly valid regex whose `[` opens a character class, so it silently
    # never matches -- and canon's rule is that a mismatched pattern times
    # out rather than erroring. This catches the pattern that would raise
    # INSIDE the confirmation step; it cannot catch the one that is merely
    # wrong, and does not pretend to.
    prompt = raw.get("wait_prompt")
    if prompt is None:
        pass  # absent and explicit null are one fact: no confirmation target
    elif not isinstance(prompt, str):
        defects.append(
            StepDefect(
                index,
                "wait_prompt",
                f"is a {type(prompt).__name__}, expected a regex string or null",
            )
        )
        prompt = None
    elif prompt == "":
        # `settle` treats a falsy wait_prompt as "no prompt at all", so an
        # empty pattern silently becomes an unconfirmed send -- on the
        # send-and-confirm path, which is one of canon's two named scars.
        # Capture never writes one (0 of 245), so this is a hand-edit, and
        # the likeliest intent behind a half-written pattern is a
        # confirmation the operator wanted.
        defects.append(
            StepDefect(
                index,
                "wait_prompt",
                "is empty -- an empty pattern is treated as NO confirmation "
                "target, not as a match-anything one; use null to mean 'none'",
            )
        )
        prompt = None
    else:
        try:
            re.compile(prompt)
        except re.error as exc:
            defects.append(
                StepDefect(index, "wait_prompt", f"is not a compilable regex ({exc.msg})")
            )
            prompt = None

    # `expected_post_class` -- the classification recorded live at capture
    # time, which replay re-classifies against. All 245 real steps carry a
    # non-empty string. With nothing to compare, the post-send confirmation
    # degrades to no confirmation at all, which is the blind pump.
    #
    # The VALUE is not policed: `unknown` appears in 3 real steps, and a
    # macro that will halt at replay (canon: an `unknown` classification is
    # itself a divergence) is a safe outcome the player owns, not a reason to
    # refuse a genuine human demonstration.
    post_class = raw.get("expected_post_class")
    if not isinstance(post_class, str) or not post_class.strip():
        if "expected_post_class" not in raw:
            kind = "is absent"
        elif not isinstance(post_class, str):
            kind = f"is a {type(post_class).__name__}"
        else:
            kind = "is blank"
        defects.append(
            StepDefect(
                index,
                "expected_post_class",
                f"{kind}, expected the screen class this send should produce",
            )
        )

    # Unrecognized keys are ignored rather than rejected -- deliberately
    # asymmetric with everything above. Refusing them would make any future
    # schema addition retroactively unplayable, and an extra key cannot cause
    # a keystroke.
    if defects:
        return None, defects
    return LoopStep(input=keystrokes, wait_prompt=prompt, expected_post_class=post_class), []


def _validate_anchor(document: Mapping[str, Any]) -> tuple[Optional[int], Optional[str]]:
    """``(anchor, None)`` or ``(None, reason)``.

    Absent / null is legal and stays ``None``: 17 of 19 real documents have
    no anchor, canon calls that a legacy macro and hands the decision to the
    player (refuse by default, explicit force to override).

    A present-but-nonsense anchor is REFUSED rather than downgraded to
    ``None``, and that is the subtlest form of the collapse this module
    guards. Downgrading looks safe, since ``None`` refuses by default -- but
    canon gives ``None`` an explicit FORCE path, and a damaged anchor must
    not inherit it: forcing past a *detected* mismatch is, in canon's words,
    "the danger itself".

    ``bool`` is excluded because ``isinstance(True, int)`` holds in Python --
    the same trap ``store._finite_number`` documents -- so an unguarded int
    check turns ``start_anchor: true`` into sector 1.

    The VALUE is not range-checked. A wrong anchor is caught live by the
    start-anchor check and halts safely, so inventing a sector range here
    would reject real macros to duplicate a guard that already exists. Only
    an UNCHECKABLE anchor -- one whose type makes the comparison meaningless
    -- is refused.
    """
    if "start_anchor" not in document:
        return None, None
    anchor = document["start_anchor"]
    if anchor is None:
        return None, None
    if isinstance(anchor, bool) or not isinstance(anchor, int):
        return None, (
            f"'start_anchor' is a {type(anchor).__name__}, expected a sector number "
            "or null -- an anchor that cannot be compared to the current sector "
            "cannot guard the replay"
        )
    return anchor, None


def _build_loop(document: Mapping[str, Any], path: Path, *, draft: bool) -> Loop:
    """Validate a matched document into a playable ``Loop``, or refuse."""
    name = document["name"]

    anchor, anchor_problem = _validate_anchor(document)
    if anchor_problem is not None:
        raise LoopMalformed(name, path, anchor_problem)

    raw_steps = document["steps"]  # a list, guaranteed by the admission gate
    if not raw_steps:
        raise LoopMalformed(
            name,
            path,
            "has no steps -- a macro with nothing to press cannot have come "
            "from a capture, and would loop forever under a repeating scope",
        )

    steps: list[LoopStep] = []
    defects: list[StepDefect] = []
    for index, raw in enumerate(raw_steps):
        step, step_defects = _validate_step(index, raw)
        if step is None:
            defects.extend(step_defects)
        else:
            steps.append(step)
    if defects:
        # FAIL-CLOSED. `steps` holds every good step and is discarded here on
        # purpose -- see the module docstring. Nothing partial escapes.
        raise LoopMalformed(
            name,
            path,
            f"{len(defects)} step problem{'' if len(defects) == 1 else 's'} "
            f"across {len(raw_steps)} steps -- the whole macro is refused, "
            "because an ordered keystroke sequence missing a step is a "
            "different macro",
            defects,
        )

    # Provenance is read, never derived. `source` stays None unless the
    # document carries one of canon's two values: `recorded` reads as "a
    # human demonstrated this at the keyboard", the single strongest claim
    # the schema makes, and it is never inferred from silence or from a
    # misspelling. `created_ts` degrades the same way -- both are displayed,
    # not acted on.
    source = document.get("source")
    created = document.get("created_ts")
    return Loop(
        name=name,
        steps=tuple(steps),
        start_anchor=anchor,
        source=source if source in SOURCE_VALUES else None,
        created_ts=created if isinstance(created, str) else None,
        draft=draft,
        path=str(path),
    )


# ---------------------------------------------------------------------------
# Finding the document
# ---------------------------------------------------------------------------


def _scan_root(directory: Path, name: str):
    """Look for ``name`` in one root.

    Returns ``(matches, blockers)``. ``matches`` is every ``(path,
    document)`` whose document CARRIES that name -- more than one is an
    ambiguity, not a pick. ``blockers`` is every candidate that could not be
    identified, each of which might have been the one asked for.

    Never raises: the failure is data, so the caller can decide whether it
    matters (it does for a miss, it does not for a hit).

    ``os.listdir``, NOT ``Path.glob``, for the reason ``store._read_root``
    documents at length: ``glob`` swallows a directory ``PermissionError``
    and returns an empty iterator, which is precisely "I was not allowed to
    look" rendering as "there is nothing here".
    """
    matches: list[tuple[Path, dict]] = []
    blockers: list[ReadFailure] = []
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        # No store has ever been written here. A genuine negative: the read
        # succeeded in establishing that there is nothing, which is a
        # different fact from failing to read.
        return matches, blockers
    except NotADirectoryError:
        return matches, [ReadFailure(str(directory), CAUSE_UNUSABLE, "not a directory")]
    except PermissionError as exc:
        return matches, [
            ReadFailure(str(directory), CAUSE_DENIED, exc.strerror or "permission denied")
        ]
    except OSError as exc:
        return matches, [
            ReadFailure(str(directory), CAUSE_UNUSABLE, exc.strerror or "could not be listed")
        ]

    for path in [directory / n for n in sorted(names) if n.endswith(".json")]:
        document, reason, cause = _read_document(path)
        if document is None:
            # Named, never silently skipped: this file might BE the loop, and
            # that is exactly what stops a miss from being asserted.
            blockers.append(ReadFailure(str(path), cause or CAUSE_CORRUPT, reason or "unreadable"))
        elif document["name"] == name:
            # Exact match only. No case-folding, no strip, no fuzzy match --
            # the name is the identity a human types to replay a macro that
            # spends credits, and "close enough" is how the wrong one runs.
            matches.append((path, document))
    return matches, blockers


def load_loop(
    name: str,
    *,
    include_drafts: bool = False,
    state_dir=None,
    skills_dir=None,
    drafts_path=None,
) -> Loop:
    """Load the taught macro called ``name``, validated for execution.

    Returns a frozen :class:`Loop` on success. Otherwise raises exactly one
    of :class:`LoopNotFound` (established absence), :class:`LoopUnreadable`
    (the search could not be completed), :class:`LoopMalformed` (found, and
    not playable) or :class:`LoopAmbiguous` (more than one claimant) -- see
    the module docstring for why those four are held apart.

    Drafts are inert proposals awaiting human approval, so they are consulted
    only when ``include_drafts`` is set, and a draft that IS returned carries
    ``draft=True`` so it can never be mistaken for a blessed macro. When a
    name is present in both places the blessed one wins, because approval is
    expressed by file location.

    Path arguments mirror ``store.read_loop_store`` exactly, so tests and the
    eventual per-world migration have one shape to learn.
    """
    blessed = Path(skills_dir) if skills_dir is not None else loops_dir(state_dir)
    roots: list[tuple[Path, bool]] = [(blessed, False)]
    if include_drafts:
        drafts = (
            Path(drafts_path)
            if drafts_path is not None
            else (blessed / DRAFTS_DIRNAME if skills_dir is not None else drafts_dir(state_dir))
        )
        roots.append((drafts, True))

    blockers: list[ReadFailure] = []
    for directory, draft in roots:
        matches, root_blockers = _scan_root(directory, name)
        blockers.extend(root_blockers)
        if len(matches) > 1:
            raise LoopAmbiguous(name, [path for path, _ in matches])
        if matches:
            # Found. The answer is established, so unreadable neighbours --
            # here or in a root not yet consulted -- are no longer relevant:
            # they could only have told us something we now know.
            path, document = matches[0]
            return _build_loop(document, path, draft=draft)

    # Not found. Whether that is a NEGATIVE or an UNKNOWN depends entirely on
    # whether the search completed, and this is the branch the whole module
    # is built around.
    if blockers:
        raise LoopUnreadable(name, blockers)
    raise LoopNotFound(name, [directory for directory, _ in roots])
