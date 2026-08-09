"""Write one taught macro from an already-observed human demonstration --
the mirror-image writer to ``loader.py``'s reader, and the ONLY module in
``loops/`` that puts a document ON DISK.

WO-P2-G4-X6. ``store.py`` and ``loader.py`` read the taught-macro store;
``player.py`` (X3) replays a validated document against a live session.
Nothing before this WO could WRITE one -- on a fresh checkout the store is,
honestly, an empty universe (``store.py``'s own docstring: "Recording a
macro (``tw record``)... [is a writer], and neither exists in the reborn
tree yet"). This module is that writer.

The stub work order's Accept line was "operator can record a loop that X2
loads" -- deliberately STRENGTHENED here, because a document can load
flawlessly and still be permanently unplayable. The real Accept this module
is built to satisfy is a ROUND TRIP TO REPLAY: record -> :func:`loader
.load_loop` -> :func:`player.replay_loop` against a scripted session ->
completes. Three defects earn a document that loads perfectly and never
plays, and each is closed STRUCTURALLY here, not by convention:

1. **``expected_post_class`` is derived, never accepted.** :meth:`LoopRecorder
   .step` takes the screen the send actually produced and calls
   ``classify.classify_screen`` on it ITSELF -- there is no parameter a
   caller could use to hand this module an invented class name. Canon's own
   illustrative macro (``canon/engine/macros.md §"A recorded macro (illustrative)"``) writes
   ``port_offer`` / ``command_prompt`` -- neither a class ``classify_screen``
   has ever emitted (measured against ``classify.py``'s live anchor tables:
   the real vocabulary has ``main_command``, not ``command_prompt``, and
   ``port_offer`` does not exist at all). A recorder that copied a class
   name from anywhere but the live classifier would silently reproduce that
   exact defect on every macro it ever wrote. No class NAME is hardcoded
   anywhere in this module or its tests, deliberately -- the live,
   authoritative set is ``classify._RETURNABLE_CLASSES`` (17 members as of
   this WO), and even that is read from the module rather than copied into
   a second list: :meth:`step` asserts its derived class is a member of it,
   belt-and-suspenders against a FUTURE edit that stopped deriving live.
2. **``wait_prompt`` is captured literally and escaped on write, never
   stored raw.** A live TW prompt (``Command [TL=00:00:00]:[3034]
   (?=Help)? :``) is full of regex metacharacters; stored verbatim as a
   regex, ``[TL=00:00:00]`` becomes a ONE-CHARACTER class over
   ``{T,L,=,0,:}`` -- it compiles cleanly (so the loader's compileability
   check cannot catch it) and then can fail to match the very screen it was
   captured from. Measured, not assumed: ``re.compile(RAW).search(RAW)`` is
   ``False`` for that exact captured string, while
   ``re.compile(re.escape(RAW)).search(RAW)`` is ``True`` -- see
   ``tests/test_loop_recorder.py``'s
   ``test_a_raw_unescaped_wait_prompt_can_fail_to_match_its_own_source_text``.
   So :meth:`LoopRecorder.step`'s ``confirm_exact=True`` path always writes
   ``re.escape(prompt_line)``, never the literal text -- the
   "capture-literal-plus-escape-on-write" strategy.
3. **A recording without a readable ``start_anchor`` never becomes a
   document at all.** :class:`LoopRecorder` reads the current sector off
   its OPENING screen at construction time and refuses -- raises
   :class:`NoStartAnchor` -- unless that read is a genuine
   ``state_parser.OUTCOME_READ``. 17 of the 19 real archived macros carry
   no anchor, which is exactly why X3's player refuses to replay them
   without an explicit human ``force`` (``player.py``'s own docstring, and
   ``FORCEABLE_HALTS == {HALT_START_ANCHOR_MISSING}``). This recorder never
   reproduces that shape: there is no way to obtain a :class:`LoopRecorder`
   whose ``start_anchor`` is ``None`` -- every document it writes carries a
   real ``int``.

Capture-only, by construction and by choice
--------------------------------------------
This module cannot send a keystroke -- ``tests/test_loop_recorder.py``
reuses ``test_loop_loader.py``'s own ``_send_violations`` scanner (the same
instrument ``loops/player.py`` is held to) and proves it clean, modulo the
SAME two-module waiver player.py earns (``classify`` / ``state_parser``,
imported for the identical reason: canon requires deriving these closed
vocabularies rather than restating them). :meth:`LoopRecorder.step` takes
the keystrokes ALREADY SENT and the screen they ALREADY PRODUCED -- by
someone else, through some other path -- and only ever writes down what it
is told. It never originates one.

This is a real, disclosed scope decision, not an oversight. A macro's
schema (``macros.md`` §Schema) needs an ``input`` field per step -- the
keystroke itself -- and this module still does not observe live presses:
it only records what a caller already supplies. Attach keystrokes *do*
land in the Trace-Ledger now (``record_attach_keystroke`` / #353), but the
recorder does not consume ledger rows into a macro. Bridging ledger→
recorder (or wiring live ``tw attach`` capture into this module) remains
follow-up that touches control-lock/driving-dispatch machinery X3/X4 own
and is outside this WO's Scope. So the boundary drawn here is: this
module turns an ALREADY-KNOWN sequence of (keystrokes, resulting screen)
pairs into a validated, storable ``Loop`` document, and the CLI verb built
on top of it (``tw record`` / ``cli.cmd_record``) supplies that sequence
from an explicit capture manifest -- itself assembled from the EXISTING,
already-shipped ``do``/``screen`` wire verbs (zero ``protocol.py``
changes). See ``cmd_record``'s own docstring for the manifest shape and
the follow-up work this leaves on the table.

Blessed, not draft -- the design call (Max-ruled 2026-07-26)
------------------------------------------------------------------
``canon/engine/macros.md`` now documents **blessed-by-default** for a
human ``tw record``: the demonstration *is* the approval. Mined /
AI-authored proposals stay drafts under ``_drafts/`` until a human
promotes them. (Older macros.md prose that said "Both are inert until
human-approved" for recorded *and* mined was the conflict this default
resolved against -- Max ruling WO-BLESSED-MACRO-DEFAULT: align docs to
code; do not flip the recorder to inert.)

Why the default was already ``blessed=True`` before that ruling:

* The schema table pairs "RECORDING a macro" with "MINING a DRAFT" -- a
  deliberate word choice that already treats the two origins differently.
* ``loader.py``'s docstring: "Approval is expressed by file location... a
  mined/AI-authored draft lives in a separate ``_drafts/`` area" -- the
  gate keeps machine-authored proposals inert, never makes a human
  re-approve their own just-performed demonstration.
* A live human demonstration *is* the strongest form of
  "human-demonstrated, human-approved"; a second promote step adds nothing.
* Practically: if every ``tw record`` required a not-yet-built promote verb
  before replay, the first writer could never satisfy Accept in non-draft
  form.

So :meth:`LoopRecorder.save` defaults to ``blessed=True``, with an explicit
``blessed=False`` (``tw record --draft``) opt-out for an operator who wants
the review ceremony anyway. **Max ruled 2026-07-26 (WO-BLESSED-MACRO-DEFAULT):
blessed-by-default is OK** -- ``macros.md`` matches; do not flip it to
inert. Every consumer already treats ``draft`` as a first-class fact
(``loader.py``, ``store.py``, ``player.py`` -- none of them special-case
``source`` directly).

Parameterization (WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2)
------------------------------------------------------------------
``canon/engine/macros.md`` §"Parameterization" wants "the concrete numbers
a human typed during one demonstration (a hold count, an offer, a sector
id)" to generalize into named placeholders bound at replay time. Before
this WO neither side of that round trip existed at all -- capture recorded
every keystroke literally and replay sent ``step.input`` verbatim, no
matter what it looked like.

:meth:`LoopRecorder.step`'s optional ``param`` argument is the capture
half: it never GUESSES which value is a parameter -- the caller (the
manifest, today ``cli.cmd_record``'s per-step ``"param"`` key) says so
explicitly, the same opt-in shape ``confirm_exact`` already uses. Scoped to
NUMERIC input only, matching canon's own examples: a non-digit
``keystrokes`` refuses rather than generalize an arbitrary command letter
into something a caller could rebind into anything. The literal value
captured becomes the parameter's recorded DEFAULT
(:meth:`LoopRecorder.document`'s ``params`` object,
``loader.py``'s ``Loop.params``) and the step's own ``input`` becomes the
placeholder text ``{name}`` -- never both, so a document's ``steps`` never
carry the literal value a caller asked to generalize away. Replay
(``loops/player.py``'s ``_apply_params``) resolves the placeholder back
into keystrokes immediately before the send it gates, preferring an
explicit override over this recorded default, and refuses to press an
unresolvable one rather than send the four literal bytes ``"{qty}"``.

Identity, and why a fourth trap does not reach this module
------------------------------------------------------------
Every document this recorder writes carries a ``name`` field equal to
EXACTLY the string :class:`LoopRecorder` was constructed with -- never
derived from, and never required to equal, the sanitized filename stem the
document is saved under. ``loader.py`` already documents why: "Resolving
``skills/<name>.json`` would be both faster and wrong... a stem is a lossy
derivation." A writer that let the two drift silently would not just risk
one dead document -- ``loader.py``'s own trichotomy means a document with
no usable ``name`` poisons every future MISS in that directory into
``LoopUnreadable`` (the search could not be completed) rather than a clean
``LoopNotFound``. :class:`LoopRecorder` cannot construct a document without
a validated, non-blank ``name`` (:class:`InvalidName`), and
``tests/test_loop_recorder.py`` proves both the positive (round-trips by
name) and the negative (a recording never poisons an unrelated MISS in the
same store).
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Optional

from ..session.classify import (
    # Disclosed coupling, not an oversight -- the same call ``loader.py``
    # makes importing ``store._read_document``: ``_RETURNABLE_CLASSES`` is
    # the private closed-set assertion ``classify.py`` already builds and
    # self-checks at import time (``assert NEVER_AUTO_ACTION_CLASSES <=
    # _RETURNABLE_CLASSES``). Re-deriving it here would be a second
    # dialect of the same fact; importing it lets :meth:`LoopRecorder.step`
    # belt-and-suspenders that ``classify_screen``'s own answer is a member
    # of its own returnable set, closing the door even on a FUTURE edit to
    # this method that stopped deriving the class live.
    _RETURNABLE_CLASSES,
    classify_screen,
)
from ..session.state_parser import OUTCOME_READ, read_current_sector
from .loader import LoopStep, is_valid_param_name
from .store import DRAFTS_DIRNAME, drafts_dir, loops_dir

__all__ = [
    "EmptyRecording",
    "InvalidName",
    "LoopRecorder",
    "LoopWriteError",
    "NoStartAnchor",
    "RecorderError",
    "promote_draft",
]


class RecorderError(Exception):
    """Base for every way a capture may refuse to become a stored loop."""


class InvalidName(RecorderError):
    """The loop name is unusable -- blank, or sanitizes to an empty
    filename stem. Refused (a blank name at construction, an unsanitizable
    one at :meth:`LoopRecorder.save`), never silently coerced into a
    placeholder identity."""


class NoStartAnchor(RecorderError):
    """The current sector could not be established from the capture's
    OPENING screen, so this recorder refuses to open the capture at all.

    Canon's start-anchor guard exists because 17 of the 19 real archived
    macros carry no anchor, and X3's player refuses to replay them without
    an explicit human ``force`` -- the LEGACY shape. This recorder never
    reproduces it: there is no way to obtain a :class:`LoopRecorder` whose
    ``start_anchor`` is ``None``. Fly to a sector whose command-prompt
    sector bracket is intact before starting a capture.
    """

    def __init__(self, read) -> None:
        self.read = read
        outcome = getattr(read, "outcome", None) or "unavailable"
        reason = getattr(read, "reason", None)
        detail = f" ({reason})" if reason else ""
        super().__init__(
            "cannot open a capture without a readable start_anchor -- the "
            f"opening screen's current-sector read was {outcome!r}{detail}. "
            "A macro recorded here would carry no precondition to re-check "
            "before replay -- exactly the legacy shape "
            "canon/engine/macros.md's start-anchor guard exists to catch, "
            "and the one this writer refuses to originate."
        )


class EmptyRecording(RecorderError):
    """:meth:`LoopRecorder.save` (or ``.document()``) was asked to finalize
    a capture that never had a single :meth:`LoopRecorder.step` call.

    Refused for the same reason ``loader.py`` refuses a stored document with
    no steps: "a macro with nothing to press cannot have come from a
    capture, and would loop forever under a repeating scope"."""


class LoopWriteError(RecorderError):
    """A draft was refused before (or while) crossing into the blessed store.

    Mirrors ``rules.writer.RuleWriteError``: promote failures are operator-
    actionable messages, never half-written blessed files.
    """


def promote_draft(
    name: str,
    *,
    state_dir=None,
    skills_dir=None,
    drafts_path=None,
    remove_draft: bool = True,
    world_id=None,
) -> Path:
    """Bless one mined/AI draft into the live skills library.

    WO-WIRE-MINED-SKILLS-PROMOTE-CLI: the skills mirror of
    ``rules.writer.promote_draft``. Approval is filesystem location — drafts
    under ``_drafts/`` are inert; this is the only product path that moves
    one into the blessed tree. Reached only from ``tw skill approve``.

    Re-validates through ``load_loop`` on the way out so a hand-edited draft
    cannot land unplayable. Never auto-called by ``miner.write_mined_draft``.
    """
    import json

    from .loader import LoopLoadError, LoopNotFound, load_loop
    from .store import migrate_flat_loops_to_world

    name = _validate_name(name)
    if skills_dir is None and world_id is not None and str(world_id).strip():
        migrate_flat_loops_to_world(str(world_id).strip(), state_dir=state_dir)
    blessed = (
        Path(skills_dir)
        if skills_dir is not None
        else loops_dir(state_dir, world_id=world_id)
    )
    drafts = (
        Path(drafts_path)
        if drafts_path is not None
        else (
            Path(skills_dir) / DRAFTS_DIRNAME
            if skills_dir is not None
            else drafts_dir(state_dir, world_id=world_id)
        )
    )

    try:
        load_loop(
            name,
            include_drafts=False,
            state_dir=state_dir,
            skills_dir=skills_dir,
            drafts_path=drafts_path,
            world_id=world_id,
        )
    except LoopNotFound:
        pass
    except LoopLoadError as exc:
        raise LoopWriteError(f"draft {name!r} is not promotable: {exc}") from None
    else:
        raise LoopWriteError(
            f"loop {name!r} is already in the blessed store at {blessed} "
            "-- promote moves drafts only"
        )

    try:
        loop = load_loop(
            name,
            include_drafts=True,
            state_dir=state_dir,
            skills_dir=skills_dir,
            drafts_path=drafts_path,
            world_id=world_id,
        )
    except LoopNotFound as exc:
        raise LoopWriteError(f"no draft named {name!r} under {drafts}") from None
    except LoopLoadError as exc:
        raise LoopWriteError(f"draft {name!r} is not promotable: {exc}") from None
    if not loop.draft:
        raise LoopWriteError(
            f"loop {name!r} resolved as blessed, not a draft -- refuse promote"
        )

    src = Path(loop.path)
    try:
        document = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LoopWriteError(f"draft {name!r} could not be read: {exc}") from None
    if not isinstance(document, dict):
        raise LoopWriteError(f"draft {name!r} is not a loop document")

    # Re-validate the bytes we are about to write (hand-edit window).
    from .loader import _build_loop

    try:
        _build_loop(document, src, draft=False)
    except LoopLoadError as exc:
        raise LoopWriteError(f"draft {name!r} is not promotable: {exc}") from None

    blessed.mkdir(parents=True, exist_ok=True)
    dest = blessed / src.name
    if dest.resolve() == src.resolve():
        raise LoopWriteError(
            f"draft {name!r} path collides with blessed destination {dest}"
        )
    _atomic_write_json(dest, document)
    if remove_draft:
        try:
            src.unlink()
        except OSError:
            pass
    return dest


def _rows_to_text_and_prompt(rows) -> tuple[str, str]:
    """``(full_text, prompt_line)`` from the wire's own ``screen`` shape.

    ``rows`` is exactly what ``protocol.build_response`` puts on the wire as
    ``resp["screen"]`` -- a list of rendered lines. Reconstructed the
    IDENTICAL way ``build_response`` does (``Session.render_text`` is
    ``"\\n".join(rows)``; the prompt line is ``rows[-1].strip()``), so a
    captured document is provably built from the same representation the
    game already produces, not a re-typed approximation of it.
    """
    if not isinstance(rows, (list, tuple)) or not all(isinstance(r, str) for r in rows):
        raise TypeError(
            "a captured screen must be the 'screen' rows list a real "
            f"tw do/screen response carries -- got {type(rows).__name__}"
        )
    full_text = "\n".join(rows)
    prompt_line = rows[-1].strip() if rows else ""
    return full_text, prompt_line


_STEM_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _sanitize_stem(name: str) -> str:
    """A filesystem-safe stem for ``name`` -- never the identity.

    Identity is the document's ``name`` field, always written verbatim
    (see this module's docstring, "Identity, and why a fourth trap does not
    reach this module"). This is ONLY the filename, and may legally differ
    from ``name`` -- ``loader.py`` scans and matches on the field, never
    the path.
    """
    stem = _STEM_UNSAFE_RE.sub("_", name).strip("_-")
    if not stem:
        raise InvalidName(
            f"loop name {name!r} sanitizes to an empty filename stem -- "
            "it needs at least one letter, digit, '_' or '-'"
        )
    return stem


def _validate_name(name) -> str:
    if not isinstance(name, str) or not name.strip():
        raise InvalidName(f"a loop needs a non-blank name -- got {name!r}")
    return name.strip()


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, document: dict) -> None:
    """Write ``document`` to ``path`` atomically -- never a half-written
    file an unlucky reader could open mid-write.

    Same idiom as ``menu/knowledge.py``'s ``save_knowledge``: a ``.tmp``
    sibling, ``os.replace`` onto the real name, cleanup on any failure --
    rather than a second, divergent atomic-write recipe. ``json.dump`` (not
    a bare ``.write()``) is deliberate here too: this module is held to the
    SAME no-send scanner ``loops/player.py`` is
    (``tests/test_loop_recorder.py``), and a bare ``.write()`` call is one
    of that scanner's blocked symbols -- calibrated for a socket's
    ``.write()``, but syntactically identical to a file's. Working the
    scanner's letter here (rather than special-casing this one call) is
    what keeps the shared instrument meaningful for the next module dropped
    into ``loops/``.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
        os.chmod(tmp_path, 0o600)
        os.replace(str(tmp_path), str(path))
        os.chmod(path, 0o600)
    except Exception:
        with suppress(OSError):
            tmp_path.unlink()
        raise


class LoopRecorder:
    """Accumulate one human demonstration into a document X2 loads and X3
    replays.

    Construction fixes the identity and the start-anchor; :meth:`step`
    appends one send's worth of what actually happened; :meth:`save` (or
    the pure :meth:`document`) finalizes. Nothing here can be un-captured --
    there is no method that removes or edits a recorded step, the same
    "capture, don't compose" posture ``player.py`` holds toward a macro it
    is replaying.
    """

    def __init__(self, name: str, opening_screen) -> None:
        self.name = _validate_name(name)
        _full_text, prompt_line = _rows_to_text_and_prompt(opening_screen)
        read = read_current_sector(prompt_line)
        if read.outcome != OUTCOME_READ:
            raise NoStartAnchor(read)
        self.start_anchor: int = read.sector
        self._steps: list[LoopStep] = []
        self._params: dict[str, str] = {}

    @property
    def steps(self) -> tuple[LoopStep, ...]:
        """Every step captured so far, read-only."""
        return tuple(self._steps)

    def step(
        self,
        keystrokes: str,
        resulting_screen,
        *,
        confirm_exact: bool = False,
        param: Optional[str] = None,
    ) -> LoopStep:
        """Record one send: ``keystrokes`` (already issued, by the CALLER,
        never by this method) and the screen it actually produced.

        ``expected_post_class`` is computed HERE, from ``resulting_screen``,
        by the same ``classify.classify_screen`` replay will re-check
        against -- never accepted as an argument, so there is no call shape
        that lets a caller hand this method an invented class (module
        docstring, trap 1).

        ``confirm_exact=True`` captures the resulting prompt line literally
        and writes ``re.escape()`` of it as ``wait_prompt`` -- never the raw
        text (trap 2). Refused when the resulting screen carries no prompt
        line at all: an empty ``wait_prompt`` is not "no confirmation
        target" to the loader, it is a malformed step (``loader.py``'s own
        validation), so this method never manufactures one.

        ``param`` (optional) generalizes THIS step's ``keystrokes`` into a
        named replay-time parameter (module docstring, "Parameterization").
        The caller names it explicitly -- this method never guesses which
        step is "the quantity" -- and it must be all-digit keystrokes
        (canon scopes parameterization to numeric input: a hold count, an
        offer, a sector id). The literal value becomes this parameter's
        recorded default and the step's own ``input`` becomes the
        placeholder ``{param}``, never both. Reusing the same ``param``
        name across two steps is legal only when the literal agrees with
        what was already captured -- disagreement would mean one recorded
        default silently overwrites another with no record either existed.
        """
        if not isinstance(keystrokes, str):
            raise TypeError(f"a step's input must be str -- got {type(keystrokes).__name__}")
        full_text, prompt_line = _rows_to_text_and_prompt(resulting_screen)
        klass = classify_screen(full_text, prompt_line)
        # Belt-and-suspenders, not a real branch today: `classify_screen`'s
        # own dispatch table can only ever answer a member of
        # `_RETURNABLE_CLASSES` (it IS that dispatch table's name set, plus
        # `unknown`), so this can never fire while the line above is what
        # produced `klass`. It exists so a FUTURE edit to this method that
        # stopped deriving the class live -- reintroducing trap 1 -- fails
        # loudly here rather than writing an unproducable class to disk.
        assert klass in _RETURNABLE_CLASSES, (
            f"classify_screen returned {klass!r}, which is not a member of its own "
            "returnable set -- refusing to persist a class the classifier itself "
            "could never produce"
        )
        if confirm_exact:
            if not prompt_line:
                raise RecorderError(
                    f"step {len(self._steps)} asked for confirm_exact=True, but the "
                    "resulting screen carries no prompt line to escape into a wait_prompt"
                )
            wait_prompt: Optional[str] = re.escape(prompt_line)
        else:
            wait_prompt = None

        if param is None:
            recorded_input = keystrokes
        else:
            if not is_valid_param_name(param):
                raise RecorderError(
                    f"step {len(self._steps)}: {param!r} is not a usable parameter name "
                    "-- it needs to start with a letter or underscore and contain only "
                    "letters, digits, and underscores"
                )
            if not keystrokes.isdigit():
                raise RecorderError(
                    f"step {len(self._steps)}: cannot generalize {keystrokes!r} into "
                    f"parameter {param!r} -- macros.md scopes parameterization to NUMERIC "
                    "input (a hold count, an offer, a sector id), and these keystrokes "
                    "are not all digits"
                )
            existing = self._params.get(param)
            if existing is not None and existing != keystrokes:
                raise RecorderError(
                    f"step {len(self._steps)}: parameter {param!r} was already captured "
                    f"with default {existing!r} at an earlier step -- this step's "
                    f"{keystrokes!r} would silently overwrite it"
                )
            self._params[param] = keystrokes
            recorded_input = "{" + param + "}"

        recorded = LoopStep(
            input=recorded_input, wait_prompt=wait_prompt, expected_post_class=klass
        )
        self._steps.append(recorded)
        return recorded

    def document(self) -> dict:
        """The plain-dict JSON document -- ``canon/engine/macros.md``
        §Schema, verbatim field names. Raises :class:`EmptyRecording` if no
        step was ever captured.

        ``params`` is written only when at least one step generalized a
        value (``step(param=...)``) -- a recording that never used the
        feature produces the EXACT document shape it always did, key for
        key, so this addition costs nothing for the overwhelming majority
        of every capture that does not opt in.
        """
        if not self._steps:
            raise EmptyRecording(
                f"loop {self.name!r} captured zero steps -- nothing was "
                "recorded between opening this capture and finalizing it"
            )
        document = {
            "name": self.name,
            "source": "recorded",
            "created_ts": _utc_now_iso(),
            "start_anchor": self.start_anchor,
            "steps": [
                {
                    "input": s.input,
                    "wait_prompt": s.wait_prompt,
                    "expected_post_class": s.expected_post_class,
                }
                for s in self._steps
            ],
        }
        if self._params:
            document["params"] = dict(self._params)
        return document

    def save(
        self,
        *,
        blessed: bool = True,
        state_dir=None,
        skills_dir=None,
        drafts_path=None,
        world_id=None,
    ) -> Path:
        """Write the finished document and return its path.

        ``blessed`` defaults to ``True`` -- see this module's docstring,
        "Blessed, not draft", for the reasoning and the disclosed canon
        ambiguity. Path arguments mirror ``loader.load_loop``'s exactly, so
        a caller (or a test) has one shape to learn for both directions of
        the round trip.
        """
        document = self.document()  # raises EmptyRecording first; nothing is written on a refusal
        from .store import migrate_flat_loops_to_world

        if skills_dir is None and world_id is not None and str(world_id).strip():
            migrate_flat_loops_to_world(str(world_id).strip(), state_dir=state_dir)
        if blessed:
            directory = (
                Path(skills_dir)
                if skills_dir is not None
                else loops_dir(state_dir, world_id=world_id)
            )
        else:
            directory = (
                Path(drafts_path)
                if drafts_path is not None
                else (
                    Path(skills_dir) / DRAFTS_DIRNAME
                    if skills_dir is not None
                    else drafts_dir(state_dir, world_id=world_id)
                )
            )
        stem = _sanitize_stem(self.name)
        path = directory / f"{stem}.json"
        _atomic_write_json(path, document)
        return path
