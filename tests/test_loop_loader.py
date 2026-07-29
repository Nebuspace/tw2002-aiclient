"""Single-loop loader (WO-P2-G4-X2).

The theme: **a macro is admitted for EXECUTION here, not for display.** Two
claims follow from that and every assertion below defends one of them.

1. *Three outcomes, never two.* "there is no loop called X", "I could not
   finish looking for X", and "X is not a playable macro" are three
   different facts and they never render alike. The collapse this repo has
   now fixed four times (``credentials`` / ``env.load_dotenv`` /
   ``get_password`` / ``daemon_alive``) is the second folding into the
   first, and a name-keyed lookup has a subtler door onto it than a
   directory listing does: a candidate file we could not open **might have
   been the one asked for**, so an unread sibling poisons a MISS even
   though it never poisons a HIT.

2. *Fail-closed on the steps.* A macro is an ordered keystroke sequence
   against a live economy. Dropping a bad step from the middle does not
   degrade it, it produces a DIFFERENT macro -- one nobody taught, whose
   remaining keystrokes land on screens the recording never saw. A
   partially-valid macro is more dangerous than an invalid one because it
   looks playable, so one bad step rejects the whole loop.

The schema constants below are measured against the 19 real archived
artifacts (16 blessed + 3 mined drafts, 245 steps), not guessed --
see ``canon/engine/macros.md`` §Schema for the contract they implement.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from tw2002_aiclient.loops import loader as loader_mod
from tw2002_aiclient.loops import store as store_mod
from tw2002_aiclient.loops.loader import (
    CAUSE_CORRUPT,
    CAUSE_DENIED,
    CAUSE_MALFORMED,
    CAUSE_UNUSABLE,
    Loop,
    LoopAmbiguous,
    LoopLoadError,
    LoopMalformed,
    LoopNotFound,
    LoopStep,
    LoopUnreadable,
    load_loop,
)

LOOPS_PKG = Path(loader_mod.__file__).resolve().parent

# The document shape the real writer emits, in the shape the 19 archived
# artifacts actually carry: every step has all three keys, `input` is always
# a str (61 of 245 are the empty string -- a bare Enter), `wait_prompt` is
# None on 206 of 245, and `expected_post_class` is a non-empty str on all
# 245.
RECORDED = {
    "name": "ore-run",
    "created_ts": "2026-07-19T06:08:23Z",
    "source": "recorded",
    "start_anchor": 158,
    "steps": [
        {"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"},
        {"input": "50", "wait_prompt": "offer", "expected_post_class": "port_offer"},
        {"input": "", "wait_prompt": None, "expected_post_class": "main_command"},
    ],
}


def _step(**over):
    base = {"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"}
    base.update(over)
    return base


def _doc(**over):
    doc = json.loads(json.dumps(RECORDED))
    doc.update(over)
    return doc


def _write_store(root: Path, docs, *, drafts=None) -> Path:
    """Build ``<root>/skills`` (and ``_drafts``) from stem -> doc-or-raw-text.

    Keys are FILE STEMS, deliberately decoupled from the documents' own
    ``name`` fields -- the two really do diverge in the archived store (see
    ``test_a_loop_is_found_by_its_document_name_not_its_filename``).
    """
    skills = root / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    for stem, body in (docs or {}).items():
        text = body if isinstance(body, str) else json.dumps(body)
        (skills / f"{stem}.json").write_text(text, encoding="utf-8")
    if drafts is not None:
        draft_dir = skills / "_drafts"
        draft_dir.mkdir(parents=True, exist_ok=True)
        for stem, body in drafts.items():
            text = body if isinstance(body, str) else json.dumps(body)
            (draft_dir / f"{stem}.json").write_text(text, encoding="utf-8")
    return skills


def _lock(request, path: Path) -> None:
    """chmod 000 with a restore finalizer, so tmp_path cleanup still works."""
    path.chmod(0o000)
    request.addfinalizer(lambda: path.chmod(0o700))


needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses the permission bits these tests depend on",
)


# --------------------------------------------------------------------------
# THE headline proof: three outcomes, three types, pairwise distinguishable
# --------------------------------------------------------------------------


@needs_unprivileged
def test_the_three_outcomes_are_three_distinct_types(tmp_path, request):
    """One store, three probes, three answers that cannot be confused.

    This is the WO's whole ask in a single test: a caller branching on the
    result can always tell "here it is" from "it isn't there" from "I could
    not find out", and no two of those share a type.

    Two stores, because the genuine miss needs a store with nothing unread
    in it -- an unidentified file in the SAME store would (correctly) turn
    outcome 2 into outcome 3, which is its own test below.
    """
    mixed, clean = tmp_path / "mixed", tmp_path / "clean"
    _write_store(mixed, {"ore-run": RECORDED, "locked": _doc(name="locked-one")})
    _write_store(clean, {"ore-run": RECORDED})
    _lock(request, mixed / "skills" / "locked.json")

    # 1. exists and parses -- and a locked neighbour does not spoil it
    hit = load_loop("ore-run", state_dir=mixed)
    assert isinstance(hit, Loop)
    assert hit.name == "ore-run"

    # 2. genuinely absent -- every candidate was read, none carried the name
    with pytest.raises(LoopNotFound) as miss:
        load_loop("no-such-loop", state_dir=clean, include_drafts=False)

    # 3. present, unreadable -- the name we want may be inside the file we
    #    could not open, so absence was never established
    with pytest.raises(LoopUnreadable) as blocked:
        load_loop("locked-one", state_dir=mixed)

    # Pairwise distinct, and neither miss-type is a subclass of the other:
    # a caller that catches one can never silently swallow the other.
    assert not isinstance(miss.value, LoopUnreadable)
    assert not isinstance(blocked.value, LoopNotFound)
    assert isinstance(miss.value, LoopLoadError)
    assert isinstance(blocked.value, LoopLoadError)

    # The failure names WHY, and names the file to fix.
    assert blocked.value.blockers
    assert any("locked.json" in b.path for b in blocked.value.blockers)
    assert any(b.cause == CAUSE_DENIED for b in blocked.value.blockers)
    assert "locked.json" in str(blocked.value)


def test_a_miss_names_what_was_actually_searched(tmp_path):
    """A miss is a claim about the roots that were CONSULTED. Saying "no
    such loop" after looking in one of two places would over-claim, so the
    roots searched travel with the exception."""
    _write_store(tmp_path, {"ore-run": RECORDED}, drafts={"mined-0": _doc(name="mined-0")})

    with pytest.raises(LoopNotFound) as blessed_only:
        load_loop("nope", state_dir=tmp_path)
    assert len(blessed_only.value.searched) == 1

    with pytest.raises(LoopNotFound) as both:
        load_loop("nope", state_dir=tmp_path, include_drafts=True)
    assert len(both.value.searched) == 2
    assert "_drafts" in "".join(both.value.searched)
    assert "nope" in str(both.value)


def test_a_never_written_store_is_a_miss_not_a_failure(tmp_path):
    """Nothing has ever been taught. That is a real, established negative --
    the read succeeded and found nothing -- so it is a miss, not an
    unreadable. The inverse of the collapse: a genuine absence must not be
    inflated into a scary failure either."""
    with pytest.raises(LoopNotFound):
        load_loop("ore-run", state_dir=tmp_path)


@needs_unprivileged
def test_a_locked_store_directory_is_never_a_missing_loop(tmp_path, request):
    """``Path.glob`` swallows a directory PermissionError and yields nothing,
    which would turn "I was not allowed to look" into "it isn't there"."""
    skills = _write_store(tmp_path, {"ore-run": RECORDED})
    _lock(request, skills)

    with pytest.raises(LoopUnreadable) as exc:
        load_loop("ore-run", state_dir=tmp_path)
    assert [b.cause for b in exc.value.blockers] == [CAUSE_DENIED]
    assert str(skills) in str(exc.value)


def test_a_file_where_the_store_should_be_is_unreadable_not_a_miss(tmp_path):
    (tmp_path / "skills").write_text("I am not a directory", encoding="utf-8")

    with pytest.raises(LoopUnreadable) as exc:
        load_loop("ore-run", state_dir=tmp_path)
    assert [b.cause for b in exc.value.blockers] == [CAUSE_UNUSABLE]
    assert "not a directory" in str(exc.value)


@pytest.mark.parametrize(
    "raw, cause",
    [
        ("{not json", CAUSE_CORRUPT),
        ('"a string"', CAUSE_MALFORMED),
        ('{"steps": []}', CAUSE_MALFORMED),
        ('{"name": "x"}', CAUSE_MALFORMED),
    ],
)
def test_a_candidate_we_could_not_identify_blocks_a_miss(tmp_path, raw, cause):
    """THE subtle door onto the four-times-fixed collapse.

    Every one of these documents fails the shared admission gate before its
    ``name`` can be trusted -- so any of them *might* be the loop asked for.
    Answering "no such loop" here asserts a negative over a file that was
    never identified.
    """
    _write_store(tmp_path, {"mystery": raw})

    with pytest.raises(LoopUnreadable) as exc:
        load_loop("ore-run", state_dir=tmp_path)
    assert [b.cause for b in exc.value.blockers] == [cause]
    assert "mystery.json" in exc.value.blockers[0].path
    assert exc.value.blockers[0].reason


def test_an_unreadable_sibling_poisons_a_miss_but_never_a_hit(tmp_path):
    """The asymmetry that makes the rule tight rather than merely loud.

    An unidentifiable file costs us the ability to say "it isn't there" --
    but once the loop IS found, the answer is established and no corrupt
    neighbour can unestablish it. A loader that failed on any unreadable
    file would be unusable in a store with one damaged document; one that
    ignored them would lie on the miss.
    """
    _write_store(tmp_path, {"ore-run": RECORDED, "broken": "{not json"})

    found = load_loop("ore-run", state_dir=tmp_path)
    assert found.name == "ore-run"

    with pytest.raises(LoopUnreadable):
        load_loop("some-other-loop", state_dir=tmp_path)


def test_a_readable_document_that_is_not_the_one_asked_for_is_just_a_miss(tmp_path):
    """The complement: a store full of perfectly readable OTHER loops
    establishes the negative, so this stays a miss and never inflates into
    an unreadable."""
    _write_store(tmp_path, {"a": _doc(name="a"), "b": _doc(name="b"), "c": _doc(name="c")})

    with pytest.raises(LoopNotFound):
        load_loop("ore-run", state_dir=tmp_path)


# --------------------------------------------------------------------------
# Identity -- the document's `name`, never the filename
# --------------------------------------------------------------------------


def test_a_loop_is_found_by_its_document_name_not_its_filename(tmp_path):
    """Measured against the real archived store: 3 of its 19 artifacts have
    a stem that is a LOSSY derivation of the document's own name (the writer
    sanitizes, and dropped a trailing underscore) -- e.g. stem
    ``mined-1-_NUM___NUM`` for name ``mined-1-_NUM___NUM_``.

    A loader that resolved ``skills/<name>.json`` would therefore miss 3
    real macros outright, and would report a stem as an identity for the
    other 16 -- adopting a lossy derivation as the thing a human types.
    """
    stem, name = "mined-1-_NUM___NUM", "mined-1-_NUM___NUM_"
    _write_store(tmp_path, {stem: _doc(name=name)})

    found = load_loop(name, state_dir=tmp_path)
    assert found.name == name
    assert found.path.endswith(f"{stem}.json")

    # And the stem is not an alias for the loop -- it is not an identity.
    with pytest.raises(LoopNotFound):
        load_loop(stem, state_dir=tmp_path)


def test_the_name_is_matched_exactly(tmp_path):
    """No case-folding, no strip, no fuzzy match. The name is the identity a
    human types to replay a macro that spends credits; "close enough" is how
    the wrong macro gets played."""
    _write_store(tmp_path, {"ore-run": _doc(name="ore-run")})

    assert load_loop("ore-run", state_dir=tmp_path).name == "ore-run"
    for near in ("Ore-Run", "ORE-RUN", " ore-run", "ore-run ", "ore", "ore-run2"):
        with pytest.raises(LoopNotFound):
            load_loop(near, state_dir=tmp_path)


def test_two_documents_claiming_one_name_refuse_rather_than_pick_one(tmp_path):
    """Reachable by hand-edit, which canon explicitly expects operators to do
    (``macros.md``: numeric generalization "currently requires a human to
    hand-edit the macro JSON"). Picking by sort order would invent an answer
    about which keystrokes to press."""
    _write_store(tmp_path, {"first": _doc(name="twin"), "second": _doc(name="twin")})

    with pytest.raises(LoopAmbiguous) as exc:
        load_loop("twin", state_dir=tmp_path)
    assert len(exc.value.paths) == 2
    assert "first.json" in str(exc.value) and "second.json" in str(exc.value)
    # Not a miss and not an unreadable -- a third, separate fact.
    assert not isinstance(exc.value, (LoopNotFound, LoopUnreadable))


def test_a_blessed_loop_outranks_a_draft_of_the_same_name(tmp_path):
    """Approval is expressed by file location (``macros.md`` findings), so a
    name present in both places resolves to the approved one."""
    _write_store(
        tmp_path,
        {"ore-run": _doc(name="ore-run", source="recorded")},
        drafts={"ore-run": _doc(name="ore-run", source="mined")},
    )

    found = load_loop("ore-run", state_dir=tmp_path, include_drafts=True)
    assert found.draft is False
    assert found.source == "recorded"
    assert "_drafts" not in found.path


# --------------------------------------------------------------------------
# Drafts -- inert, opt-in, and never mistakable for an approved macro
# --------------------------------------------------------------------------


def test_a_draft_is_not_reachable_unless_asked_for(tmp_path):
    _write_store(tmp_path, {}, drafts={"mined-0": _doc(name="mined-0", source="mined")})

    with pytest.raises(LoopNotFound):
        load_loop("mined-0", state_dir=tmp_path)

    found = load_loop("mined-0", state_dir=tmp_path, include_drafts=True)
    assert found.draft is True
    assert found.source == "mined"


# --------------------------------------------------------------------------
# Step validation -- FAIL-CLOSED, and it reports every defect it found
# --------------------------------------------------------------------------


def test_one_bad_step_rejects_the_whole_loop(tmp_path):
    """The core strictness ruling. Steps 0/1/3 are perfectly good; the loop
    is still refused, because playing 0,1,3 means pressing step 3's key
    against the screen step 2 was supposed to produce -- the blind pump
    ``macros.md`` invariant 2 exists to make impossible."""
    doc = _doc(
        name="four",
        steps=[
            _step(input="P"),
            _step(input="S"),
            _step(input=50),  # the one bad step: a number, not keystrokes
            _step(input="Q"),
        ],
    )
    _write_store(tmp_path, {"four": doc})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("four", state_dir=tmp_path)

    assert exc.value.cause == CAUSE_MALFORMED
    assert [d.index for d in exc.value.defects] == [2]
    assert exc.value.defects[0].field == "input"
    # No partially-valid macro is reachable from the failure -- the good
    # steps are not handed back in any form a caller could press.
    assert not hasattr(exc.value, "steps")
    assert not hasattr(exc.value, "loop")


def test_every_defect_is_reported_not_only_the_first(tmp_path):
    """Fail-closed on safety, complete on diagnostics: refusing the loop is
    the safe half, but an operator fixing the JSON should see every problem
    in one pass rather than rediscovering them one run at a time."""
    doc = _doc(
        name="messy",
        steps=[
            _step(input=None),
            _step(wait_prompt="(unclosed"),
            _step(expected_post_class=""),
            _step(),
        ],
    )
    _write_store(tmp_path, {"messy": doc})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("messy", state_dir=tmp_path)

    assert [d.index for d in exc.value.defects] == [0, 1, 2]
    assert [d.field for d in exc.value.defects] == [
        "input",
        "wait_prompt",
        "expected_post_class",
    ]
    assert all(d.reason for d in exc.value.defects)
    assert "3" in str(exc.value)  # the count reaches the operator


@pytest.mark.parametrize(
    "bad_input",
    [50, None, True, ["P"], {"key": "P"}, 1.5],
)
def test_an_input_that_is_not_keystrokes_is_a_defect(tmp_path, bad_input):
    """``input`` is "the keystroke(s) to send" (``macros.md`` §Schema). A
    non-string would be stringified somewhere downstream and pressed as
    whatever ``str()`` produced -- ``True`` would send ``"True"``."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(input=bad_input)])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects[0].field == "input"


def test_a_missing_input_key_is_a_defect(tmp_path):
    step = {"wait_prompt": None, "expected_post_class": "port_trade"}
    _write_store(tmp_path, {"x": _doc(name="x", steps=[step])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects[0].field == "input"


def test_an_empty_input_is_legal_because_it_is_a_bare_enter(tmp_path):
    """Canon lists ``""`` explicitly as "bare Enter/accept-default", and 61
    of the archived store's 245 real steps are exactly that. A truthiness
    check on ``input`` would reject a quarter of the real corpus."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(input="")])})

    loop = load_loop("x", state_dir=tmp_path)
    assert loop.steps[0].input == ""


@pytest.mark.parametrize("absent", [None, "omit"])
def test_no_wait_prompt_is_legal_and_stays_none(tmp_path, absent):
    """"Most recorded steps carry none" (canon) -- 206 of 245 in the real
    store. Absent and explicit-null are the same fact here."""
    step = _step()
    if absent == "omit":
        step.pop("wait_prompt")
    _write_store(tmp_path, {"x": _doc(name="x", steps=[step])})

    assert load_loop("x", state_dir=tmp_path).steps[0].wait_prompt is None


@pytest.mark.parametrize("pattern", ["(unclosed", "[a-", "*bad", "(?P<>x)"])
def test_an_uncompilable_wait_prompt_is_a_defect(tmp_path, pattern):
    """A ``wait_prompt`` is compiled on the send path. Left to replay, this
    raises INSIDE the confirmation step -- the one place canon requires a
    positive answer before the next keystroke goes out."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(wait_prompt=pattern)])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects[0].field == "wait_prompt"


def test_an_empty_wait_prompt_is_a_defect_not_a_silent_no_prompt(tmp_path):
    """``settle`` treats a falsy ``wait_prompt`` as "no prompt at all", so an
    empty pattern would silently become an unconfirmed send. Capture never
    writes one (0 of 245), so it is a hand-edit -- and the likeliest intent
    behind a half-written pattern is a confirmation the operator wanted."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(wait_prompt="")])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects[0].field == "wait_prompt"


def test_a_wait_prompt_is_kept_verbatim_and_case_sensitively(tmp_path):
    """HARD RULE (``canon/engine/macros.md``, ``settle-detection.md``):
    ``wait_prompt`` regexes are case-sensitive, and a mismatched pattern
    silently times out rather than erroring. Normalizing case here would
    change which screen a macro confirms against."""
    pattern = r"Command \[TL="  # a real pattern from the archived store
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(wait_prompt=pattern)])})

    assert load_loop("x", state_dir=tmp_path).steps[0].wait_prompt == pattern


@pytest.mark.parametrize("bad", ["", "   ", None, 7, ["port_trade"]])
def test_a_missing_expected_post_class_is_a_defect(tmp_path, bad):
    """All 245 real steps carry a non-empty string. Replay re-classifies the
    settled screen and COMPARES against this; with nothing to compare, the
    post-send confirmation silently degrades to no confirmation."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(expected_post_class=bad)])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects[0].field == "expected_post_class"


def test_expected_post_class_unknown_is_accepted_because_the_real_store_has_it(tmp_path):
    """3 of the 245 archived steps recorded ``unknown``. That macro will halt
    at replay (canon: an ``unknown`` classification IS a divergence) -- which
    is a SAFE outcome the player owns, not a reason for the loader to refuse
    a genuine human demonstration."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[_step(expected_post_class="unknown")])})

    assert load_loop("x", state_dir=tmp_path).steps[0].expected_post_class == "unknown"


@pytest.mark.parametrize("bad", ["P", 3, None, ["input"]])
def test_a_step_that_is_not_an_object_is_a_defect(tmp_path, bad):
    _write_store(tmp_path, {"x": _doc(name="x", steps=[bad])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects[0].index == 0


def test_a_loop_with_no_steps_is_not_a_program(tmp_path):
    """The store LISTS a zero-step document happily -- listing is display.
    Admitting one for execution is different: it cannot have come from a
    capture (capture appends a step per keystroke, and the real corpus'
    minimum is 1), and under ``scope: repeating`` it is a loop that spins
    forever pressing nothing."""
    _write_store(tmp_path, {"x": _doc(name="x", steps=[])})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert exc.value.defects == ()
    assert "no steps" in str(exc.value)


def test_unknown_step_keys_are_ignored_not_rejected(tmp_path):
    """Forward compatibility, deliberately asymmetric with the strictness
    above: refusing unrecognized keys would make any future schema addition
    retroactively unplayable, and an extra key cannot cause a keystroke."""
    step = _step(note="added by a later writer")
    _write_store(tmp_path, {"x": _doc(name="x", steps=[step])})

    loop = load_loop("x", state_dir=tmp_path)
    assert loop.steps[0].input == "P"
    assert not hasattr(loop.steps[0], "note")


# --------------------------------------------------------------------------
# start_anchor -- the precondition, never invented and never guessed
# --------------------------------------------------------------------------


def test_an_absent_anchor_loads_as_none_and_is_never_invented(tmp_path):
    """17 of the 19 archived documents carry NO ``start_anchor`` at all.

    Canon calls that a legacy macro and gives it an explicit path -- "refuses
    to replay by default ... the only way past is an explicit force" -- so
    rejecting it here would refuse 89% of the real store, and defaulting an
    anchor into existence would manufacture the very precondition the guard
    exists to check.
    """
    doc = _doc(name="legacy")
    doc.pop("start_anchor")
    _write_store(tmp_path, {"legacy": doc, "nulled": _doc(name="nulled", start_anchor=None)})

    assert load_loop("legacy", state_dir=tmp_path).start_anchor is None
    assert load_loop("nulled", state_dir=tmp_path).start_anchor is None


def test_a_real_anchor_survives_as_an_int(tmp_path):
    assert load_loop(
        "ore-run", state_dir=_written(tmp_path, {"ore-run": RECORDED})
    ).start_anchor == 158


def _written(tmp_path, docs):
    _write_store(tmp_path, docs)
    return tmp_path


@pytest.mark.parametrize("bad", ["158", True, False, {"sector": 158}, [158], 1.5])
def test_an_uncheckable_anchor_is_refused_not_quietly_treated_as_absent(tmp_path, bad):
    """The collapse wearing its subtlest disguise.

    Downgrading a damaged anchor to ``None`` looks safe -- ``None`` refuses
    to replay by default. But canon gives ``None`` an explicit FORCE path,
    and a damaged anchor must not inherit it: forcing past a detected
    mismatch is, in canon's words, "the danger itself". A present-but-
    nonsense anchor is a damaged document, not a legacy one.

    ``True``/``False`` are in here because ``isinstance(True, int)`` holds in
    Python -- the same trap ``store._finite_number`` documents -- so an
    unguarded int check turns ``start_anchor: true`` into sector 1.
    """
    _write_store(tmp_path, {"x": _doc(name="x", start_anchor=bad)})

    with pytest.raises(LoopMalformed) as exc:
        load_loop("x", state_dir=tmp_path)
    assert "start_anchor" in str(exc.value)


def test_the_anchor_value_itself_is_not_range_checked(tmp_path):
    """Deliberate line: a WRONG anchor is caught live by the start-anchor
    check and halts safely, so inventing a sector-range here would reject
    real macros to duplicate a guard that already exists. Only an
    UNCHECKABLE anchor (wrong type) is refused."""
    _write_store(tmp_path, {"x": _doc(name="x", start_anchor=-5)})

    assert load_loop("x", state_dir=tmp_path).start_anchor == -5


# --------------------------------------------------------------------------
# The asymmetry rule: acted-on fields fail closed, displayed fields degrade
# --------------------------------------------------------------------------


def test_provenance_degrades_to_unknown_while_the_anchor_refuses(tmp_path):
    """One document, both kinds of damage, two different treatments -- which
    is the rule stated as a test: a field the player must ACT on is
    fail-closed; a field that is only DISPLAYED degrades to unknown rather
    than blocking a playable macro.

    ``source`` is never defaulted to ``recorded`` -- the strongest claim the
    schema makes ("a human demonstrated this at the keyboard"), which the
    store already refuses to invent from silence.
    """
    _write_store(
        tmp_path,
        {
            "a": _doc(name="a", source="invented", created_ts=12345),
            "b": _doc(name="b", start_anchor="158"),
        },
    )

    degraded = load_loop("a", state_dir=tmp_path)
    assert degraded.source is None
    assert degraded.created_ts is None

    with pytest.raises(LoopMalformed):
        load_loop("b", state_dir=tmp_path)


def test_a_missing_source_is_unknown_never_recorded(tmp_path):
    doc = _doc(name="x")
    doc.pop("source")
    _write_store(tmp_path, {"x": doc})

    assert load_loop("x", state_dir=tmp_path).source is None


# --------------------------------------------------------------------------
# The artifact handed to the player is immutable
# --------------------------------------------------------------------------


def test_a_loaded_loop_cannot_be_edited_after_validation(tmp_path):
    """Validation is worthless if the thing validated can be rewritten before
    it is pressed. Frozen all the way down -- ``steps`` is a tuple, not a
    list, because ``frozen=True`` does not deep-freeze a mutable field."""
    _write_store(tmp_path, {"ore-run": RECORDED})
    loop = load_loop("ore-run", state_dir=tmp_path)

    assert isinstance(loop.steps, tuple)
    assert all(isinstance(s, LoopStep) for s in loop.steps)
    with pytest.raises(Exception):
        loop.name = "other"
    with pytest.raises(Exception):
        loop.steps[0].input = "X"
    with pytest.raises(AttributeError):
        loop.steps.append(LoopStep(input="X", wait_prompt=None, expected_post_class="c"))


def test_the_whole_recorded_document_round_trips(tmp_path):
    """One end-to-end read of the canonical shape, so the field-by-field
    tests above cannot all pass while the assembled structure is wrong."""
    _write_store(tmp_path, {"ore-run": RECORDED})
    loop = load_loop("ore-run", state_dir=tmp_path)

    assert loop.name == "ore-run"
    assert loop.source == "recorded"
    assert loop.created_ts == "2026-07-19T06:08:23Z"
    assert loop.start_anchor == 158
    assert loop.draft is False
    assert loop.path.endswith("ore-run.json")
    assert [s.input for s in loop.steps] == ["P", "50", ""]
    assert [s.wait_prompt for s in loop.steps] == [None, "offer", None]
    assert [s.expected_post_class for s in loop.steps] == [
        "port_trade",
        "port_offer",
        "main_command",
    ]


# --------------------------------------------------------------------------
# Explicit-path seams, matching `read_loop_store`'s own signature
# --------------------------------------------------------------------------


def test_explicit_directories_are_honored(tmp_path):
    skills = tmp_path / "elsewhere"
    skills.mkdir()
    (skills / "ore-run.json").write_text(json.dumps(RECORDED), encoding="utf-8")

    assert load_loop("ore-run", skills_dir=skills).name == "ore-run"


def test_non_json_files_are_not_candidates(tmp_path):
    """A README or a swapfile in the store is not an unidentified macro, so
    it must not block a miss -- the honest-negative rule cuts both ways."""
    skills = _write_store(tmp_path, {})
    (skills / "README.md").write_text("notes", encoding="utf-8")
    (skills / "ore-run.json.bak").write_text("{not json", encoding="utf-8")

    with pytest.raises(LoopNotFound):
        load_loop("ore-run", state_dir=tmp_path)


# --------------------------------------------------------------------------
# Structural pins -- the bounds this slice was built inside
# --------------------------------------------------------------------------

# Symbols that can put a keystroke on the wire, in the shape
# tests/test_spectate_no_send.py already established for the cockpit.
#
# `send_and_confirm` was added by WO-P2-G4-X3. It is deliberately IN this
# set even though the player is allowed exactly one of them: the pin is
# stronger when the player's single send is REPORTED by the same scanner
# that forbids the others, rather than invisible to it. A blocklist that
# did not name the one call that actually reaches the wire would pass on
# the player for the wrong reason.
_SEND_SYMBOLS = frozenset({
    "send_key", "send_raw", "send_request", "sendall", "send",
    "AttachInputConn", "attach_client", "cmd_do", "cmd_send", "write",
    "send_and_confirm",
})

# `loops/` modules that must not reach the transport AT ALL -- the strict
# pin, unchanged from G3/X2. `player.py` and `recorder.py` are each held to
# their OWN (and separately proven) pin, in tests/test_loop_player.py and
# tests/test_loop_recorder.py respectively; both are named here, not merely
# skipped, so neither exclusion can be silent (WO-P2-G4-X6: this is the
# "someone decides, explicitly, which pin a new module belongs under"
# moment the test below's own docstring anticipates -- recorder.py writes
# files, so it fits neither the zero-writes read-only pin nor player's own
# `test_no_run_loop_snuck_in` no-persistence claim; it earns a third).
_READ_ONLY_MODULES = frozenset({"__init__.py", "store.py", "loader.py", "list_view.py"})
_PLAYER_MODULE = "player.py"
_RECORDER_MODULE = "recorder.py"


def _reflected_name(call):
    """``getattr(o, "send_raw")`` / ``o.__getattribute__("send_raw")`` with a
    STRING-LITERAL name -- the alias/reflection door a plain Attribute match
    never sees. Dynamic names stay a disclosed residual gap, as they are for
    every static scanner."""
    if isinstance(call.func, ast.Name) and call.func.id in {"getattr", "setattr"}:
        if len(call.args) >= 2:
            arg = call.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
    if (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "__getattribute__"
        and call.args
    ):
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _send_violations(
    source: str, allow_session_modules=frozenset(), allow_package_modules=frozenset()
) -> list[str]:
    """Every way this scanner knows of to reach the wire from a module.

    Two layers, and the FIRST is the load-bearing one: a module that cannot
    import the transport cannot send through it, whatever it names its
    variables. The symbol blocklist is the backstop for a send path that
    somehow arrives without importing ``session``.

    ``allow_session_modules`` waives the import ban for named ``session``
    submodules, and ONLY in the single relative spelling ``from ..session.X
    import ...`` -- an absolute ``import tw2002_aiclient.session.X`` stays a
    violation, so the waiver cannot be reached by a second route. It exists
    for ``loops/player.py``, which canon requires to DERIVE closed
    vocabularies from ``classify`` / ``state_parser`` rather than restate
    them. The waiver is not taken on trust: the caller that passes it also
    runs this scanner over the waived modules themselves (see
    ``tests/test_loop_player.py``), so a send appearing in one of them fails
    there rather than silently widening the pin here.
    """
    tree = ast.parse(source)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in {"socket", "telnetlib"} or ".session" in f".{alias.name}":
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            parts = mod.split(".")
            if len(parts) == 2 and parts[0] == "session" and parts[1] in allow_session_modules:
                continue
            # WO-HALT-QUALIFY-CONSOLIDATE: same waiver discipline, one level up.
            # A package-root leaf (`from ..halt_reasons import ...`) is allowed
            # ONLY when named here, ONLY in this single relative spelling, and
            # ONLY because the caller granting it also runs this scanner over
            # the waived module itself -- see `tests/test_loop_player.py`. A
            # module that cannot import the transport cannot send through it,
            # and that is proven for the waived module rather than assumed.
            if len(parts) == 1 and parts[0] in allow_package_modules:
                continue
            if parts[0] in {"socket", "telnetlib"} or "session" in parts:
                bad.append(f"from {mod} import ...")
            # `from ..session import cli` -- a relative hop out of the package.
            if node.level and node.level > 1:
                bad.append(f"relative import above the package: level {node.level}")
        elif isinstance(node, ast.Attribute) and node.attr in _SEND_SYMBOLS:
            bad.append(f".{node.attr}")
        elif isinstance(node, ast.Name) and node.id in _SEND_SYMBOLS:
            bad.append(node.id)
        elif isinstance(node, ast.Call):
            name = _reflected_name(node)
            if name in _SEND_SYMBOLS:
                bad.append(f"reflected {name}")
    return bad


def test_the_read_modules_still_cannot_send_a_keystroke(tmp_path):
    """``loops/__init__.py`` claims the read modules "still cannot send at
    all". This is that claim, enforced rather than asserted.

    It is also the guarantee that keeps this lane disjoint from the live
    ``protocol.py`` lane: a READ module in ``loops/`` reaching into
    ``session/`` is exactly the edge that would couple them.

    ``player.py`` (WO-P2-G4-X3) and ``recorder.py`` (WO-P2-G4-X6) are each
    held to their own, DIFFERENT pin, proven in ``tests/test_loop_player.py``
    and ``tests/test_loop_recorder.py`` respectively. Both exclusions are by
    NAME, and the coverage assertion below is an equality rather than a
    superset: a new module dropped into ``loops/`` fails here until someone
    decides, explicitly, which pin it belongs under. That is what stops the
    strict pin from being escaped by simply adding a file.
    """
    scanned = sorted(LOOPS_PKG.glob("*.py"))
    assert {p.name for p in scanned} == _READ_ONLY_MODULES | {_PLAYER_MODULE, _RECORDER_MODULE}

    for path in scanned:
        if path.name in (_PLAYER_MODULE, _RECORDER_MODULE):
            continue
        assert _send_violations(path.read_text(encoding="utf-8")) == [], path.name

    # The prose pin the WO requires stays in place, in its own words.
    from tw2002_aiclient import loops as loops_pkg

    assert "cannot send at all" in (loops_pkg.__doc__ or "")


def test_the_no_send_scanner_actually_fires():
    """Positive control. Without this the guard above passes on an empty
    scan, a broken parse, or a blocklist that matches nothing -- "green"
    would mean "found nothing" rather than "there is nothing"."""
    assert _send_violations("from ..session import cli") != []
    assert _send_violations("from tw2002_aiclient.session import protocol") != []
    assert _send_violations("import socket") != []
    assert _send_violations("conn.send_raw('P')") != []
    assert _send_violations("getattr(conn, 'send_key')('P')") != []
    assert _send_violations("port.send_and_confirm('P', None)") != []
    # ... and stays quiet on what this package actually does.
    assert _send_violations("from .store import _read_document\nimport os, re, json") == []


def test_the_session_import_waiver_is_narrow():
    """The waiver `player.py` relies on, pinned from the other side.

    It must open exactly one door and no more: the relative
    ``from ..session.<allowed> import ...`` spelling, for a NAMED module
    only. Everything else about the session import ban has to keep firing,
    or the waiver becomes a general-purpose hole the day someone passes a
    wider set.
    """
    allow = frozenset({"classify"})
    assert _send_violations("from ..session.classify import classify_screen", allow) == []
    # A different session module is still refused, even under a waiver.
    assert _send_violations("from ..session.protocol import build_response", allow) != []
    # The absolute spelling of the very same allowed module is still refused.
    assert _send_violations("import tw2002_aiclient.session.classify", allow) != []
    assert _send_violations("from tw2002_aiclient.session.classify import x", allow) != []
    # The waiver never touches the symbol blocklist.
    assert _send_violations("from ..session.classify import x\nc.sendall(b'P')", allow) != []
    # Or the transport ban.
    assert _send_violations("import socket", allow) != []


def _existence_probes(source: str) -> list[str]:
    """Calls that ASK whether a path is there instead of opening it."""
    banned = {"exists", "is_file", "is_dir"}
    return [
        n.func.attr
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in banned
    ]


def test_the_loader_never_asks_whether_a_path_exists():
    """``Path.exists()`` is the usual culprit for the exact collapse this
    module exists to prevent: it answers False for a file that is
    demonstrably there under an unreadable directory (measured in
    ``909ab01``), turning "denied" into "absent". The loader opens and
    classifies instead.

    The positive control is not optional here -- without it this passes just
    as happily on a scanner that matches nothing at all.
    """
    assert _existence_probes("if path.exists(): read(path)") == ["exists"]
    assert _existence_probes("if p.is_file(): pass") == ["is_file"]
    assert _existence_probes("open(path)") == []

    assert _existence_probes((LOOPS_PKG / "loader.py").read_text(encoding="utf-8")) == []
    # The sibling it shares the store with must stay clean too, or the
    # collapse simply moves one file over.
    assert _existence_probes((LOOPS_PKG / "store.py").read_text(encoding="utf-8")) == []


def test_the_shared_document_gate_is_shared_not_reimplemented():
    """The loader deliberately imports ``store``'s admission gate rather than
    growing a second copy that can drift -- the same disclosed-coupling call
    ``env.py`` made for ``credentials._decoder_detail``. This pins the name
    so a rename fails here rather than silently forking the gate."""
    assert loader_mod._read_document is store_mod._read_document
    assert loader_mod.SOURCE_VALUES is store_mod.SOURCE_VALUES

    document, reason, cause = store_mod._read_document(Path(store_mod.__file__))
    assert document is None and reason and cause == CAUSE_CORRUPT


def test_no_writer_and_no_player_snuck_in(tmp_path):
    """The slice boundary, enforced: X2 is a loader. Recording is X6 and
    playing is X3/X4, and neither is licensed here."""
    source = (LOOPS_PKG / "loader.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    writes = [
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in {"write_text", "write_bytes", "mkdir", "unlink", "rename", "dump"}
    ]
    assert writes == []
    assert "def play" not in source and "def record" not in source

    # And an actual read leaves the store byte-identical.
    skills = _write_store(tmp_path, {"ore-run": RECORDED})
    before = sorted((p.name, p.read_bytes()) for p in skills.glob("*.json"))
    load_loop("ore-run", state_dir=tmp_path)
    assert sorted((p.name, p.read_bytes()) for p in skills.glob("*.json")) == before


def test_the_store_listing_surface_is_unchanged(tmp_path):
    """The loader shares ``store``'s internals, so this pins that sharing did
    not move the listing's own answers -- the G3 surface is proven and this
    slice is not entitled to change it."""
    _write_store(tmp_path, {"ore-run": RECORDED, "broken": "{not json"})
    result = store_mod.read_loop_store(state_dir=tmp_path)

    assert result["status"] == "partial"
    assert [row["name"] for row in result["loops"]] == ["ore-run"]
    assert result["unreadable"][0]["reason"].startswith("invalid JSON")
