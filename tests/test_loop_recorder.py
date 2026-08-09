"""Loop recorder (WO-P2-G4-X6) -- the writer that ends the empty universe.

The stub WO's Accept was "operator can record a loop that X2 loads" -- this
suite holds it to the STRENGTHENED version instead: record -> the real X2
loader -> the real X3 player against a scripted fake session -> completes.
A document that loads but cannot replay is not a pass here; see
``test_recorded_loop_round_trips_through_the_loader_into_a_completed_replay``,
the headline proof.

Four defect classes make a document load-but-never-play, and each earns its
own isolating pin below (never trust the round trip alone to have caught
them all):

1. an INVENTED ``expected_post_class`` (never the live classifier's answer)
2. a RAW, unescaped ``wait_prompt`` (compiles; silently mismatches)
3. a DROPPED ``start_anchor`` (the archive's own 17-of-19 defect)
4. a document with no usable ``name`` (poisons every future MISS in its
   store into ``LoopUnreadable`` rather than a clean ``LoopNotFound`` --
   ``loader.py``'s own trichotomy, measured by the dispatcher against this
   tip and folded in here as an addendum)

``LoopRecorder`` is built so none of the four is reachable through its own
API; this file proves the positive (each defect is structurally absent) and,
where the defect is a live phenomenon rather than a design choice (traps 1
and 2), also proves the underlying danger by EXECUTION rather than by
citing the docstring.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tw2002_aiclient.loops import recorder as recorder_mod
from tw2002_aiclient.loops.loader import LoopNotFound, LoopStep, LoopUnreadable, load_loop
from tw2002_aiclient.loops.player import OUTCOME_COMPLETED, replay_loop
from tw2002_aiclient.loops.recorder import (
    EmptyRecording,
    InvalidName,
    LoopRecorder,
    NoStartAnchor,
    RecorderError,
)
from tw2002_aiclient.session.classify import classify_screen
from tw2002_aiclient.session.state_parser import (
    OUTCOME_ABSENT,
    OUTCOME_READ,
    OUTCOME_UNREADABLE,
    read_current_sector,
)

# Reused, not forked -- the same instrument `loops/player.py` is held to
# (test_loop_player.py does the same reuse from test_loop_loader.py).
from .test_loop_loader import _send_violations
from .test_loop_player import ScriptedSession

RECORDER_SRC = Path(recorder_mod.__file__).read_text(encoding="utf-8")
ALLOWED_SESSION_MODULES = frozenset({"classify", "state_parser"})


# ---------------------------------------------------------------------------
# Screen fixtures -- the wire's own `screen` (rows) shape, not a
# pre-joined string: `LoopRecorder` takes exactly what a real `tw do`/
# `tw screen --json` response's `"screen"` field carries.
# ---------------------------------------------------------------------------

_SECTOR_BODY = (
    "Sector  : 158 in uncharted space.\n"
    "Ports   : Aegis, Class 1 (BBS)\n"
    "Warps to Sector(s) :  231 - 4309\n"
)
PROMPT_158 = "Command [TL=00:00:00]:[158] (?=Help)? :"
# PROMPT_158 already carries `[`, `]`, `(`, `)`, `?` -- appending a decoration
# adds the sixth metacharacter the brief asks for (`.`) without disturbing
# the sector-bracket regex `read_current_sector` anchors on (it only cares
# about `command [tl=...]:[NUMBER]` and ignores everything after the close
# bracket).
PROMPT_158_METACHAR = PROMPT_158 + " rev.2"
PROMPT_CLASSIC = "Command [TL=00753:0/0/0/850] (?=Help)? :"  # sector ABSENT
PROMPT_DAMAGED = "Command [TL=00:00:00]:["  # sector UNREADABLE (opened, unresolved)

_PORT_BODY = "Docking...\n\nCommerce report for Aegis: 1 Fuel Ore, Organics, Equipment\n\n"
PROMPT_PORT = "<Trade with this port> (Y/N)? "


def _rows(body: str, prompt_line: str) -> list[str]:
    """The wire's own `screen` shape: body lines, then the current prompt."""
    return body.splitlines() + [prompt_line]


def _text_and_prompt(rows: list[str]) -> tuple[str, str]:
    """What `player.ScriptedSession` and `classify_screen` want -- derived
    the SAME way `recorder._rows_to_text_and_prompt` (and, upstream,
    `protocol.build_response`) derive it, so a fixture used on both sides of
    a round trip cannot quietly diverge from what the recorder itself saw."""
    return "\n".join(rows), (rows[-1].strip() if rows else "")


ANCHOR_158 = _rows(_SECTOR_BODY, PROMPT_158)
ANCHOR_158_METACHAR = _rows(_SECTOR_BODY, PROMPT_158_METACHAR)
CLASSIC = _rows(_SECTOR_BODY, PROMPT_CLASSIC)
DAMAGED = _rows(_SECTOR_BODY, PROMPT_DAMAGED)
PORT = _rows(_PORT_BODY, PROMPT_PORT)


def test_the_fixtures_classify_as_this_file_assumes():
    """Re-derived from the live code, never trusted from a comment --
    the same suite-green-is-not-coverage guard test_loop_player.py runs for
    its own fixtures."""
    assert classify_screen(*_text_and_prompt(ANCHOR_158)) == "main_command"
    assert classify_screen(*_text_and_prompt(ANCHOR_158_METACHAR)) == "main_command"
    assert classify_screen(*_text_and_prompt(PORT)) == "port_trade"

    assert read_current_sector(_text_and_prompt(ANCHOR_158)[1]).outcome == OUTCOME_READ
    assert read_current_sector(_text_and_prompt(ANCHOR_158)[1]).sector == 158
    assert read_current_sector(_text_and_prompt(ANCHOR_158_METACHAR)[1]).sector == 158
    assert read_current_sector(_text_and_prompt(CLASSIC)[1]).outcome == OUTCOME_ABSENT
    assert read_current_sector(_text_and_prompt(DAMAGED)[1]).outcome == OUTCOME_UNREADABLE


# ---------------------------------------------------------------------------
# Trap 3 -- a real start_anchor, or no document at all
# ---------------------------------------------------------------------------


def test_opening_a_capture_captures_the_real_start_anchor():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    assert rec.start_anchor == 158
    assert rec.name == "ore-run"
    assert rec.steps == ()


@pytest.mark.parametrize(
    "screen,outcome",
    [(CLASSIC, "absent"), (DAMAGED, "unreadable")],
    ids=["current-sector-absent", "current-sector-unreadable"],
)
def test_opening_a_capture_without_a_readable_sector_refuses(screen, outcome):
    """Neither 'the screen makes no claim' nor 'a claim we could not
    resolve' is a start_anchor this recorder will ever write -- both halt
    the capture before it becomes an object at all."""
    with pytest.raises(NoStartAnchor) as excinfo:
        LoopRecorder("ore-run", screen)
    assert excinfo.value.read.outcome == outcome


def test_a_blank_name_is_refused_at_construction():
    for bad in ("", "   ", None, 42, 4.5):
        with pytest.raises(InvalidName):
            LoopRecorder(bad, ANCHOR_158)


def test_a_non_screen_opening_value_is_refused():
    for bad in (None, "not-a-list", 42, [1, 2]):
        with pytest.raises(TypeError):
            LoopRecorder("ore-run", bad)


# ---------------------------------------------------------------------------
# Trap 1 -- expected_post_class is derived, never invented
# ---------------------------------------------------------------------------


def test_expected_post_class_is_derived_live_never_invented():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    step = rec.step("P", PORT)

    assert step.expected_post_class == classify_screen(*_text_and_prompt(PORT))
    assert step.expected_post_class == "port_trade"
    # And specifically NOT canon's own illustrative (but non-emitting)
    # spelling for this exact shape (macros.md:180-183) -- the defect a
    # class-name-from-a-table recorder would silently reproduce on every
    # macro it ever wrote.
    assert step.expected_post_class != "command_prompt"
    assert step.expected_post_class != "port_offer"


def test_step_returns_the_loaders_own_LoopStep_type():
    """Not a duplicated dataclass -- the SAME type the loader hands back
    after a round trip through JSON, so a document's steps and a fresh
    capture's steps are directly comparable."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    step = rec.step("P", PORT)
    assert isinstance(step, LoopStep)


def test_a_non_str_input_is_refused():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    with pytest.raises(TypeError):
        rec.step(50, PORT)  # an int keystroke -- the same trap loader.py guards on read


def test_the_derived_class_is_always_a_member_of_classifys_own_returnable_set():
    """The dispatcher's sharpened brief: the class list itself is not to be
    trusted from any table (including canon's own), only from the live
    classifier. This is the positive half -- every class this module ever
    produces is a genuine member of ``classify.py``'s own closed set."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    step = rec.step("P", PORT)
    assert step.expected_post_class in recorder_mod._RETURNABLE_CLASSES


def test_a_class_outside_the_returnable_set_is_refused_even_if_somehow_produced(monkeypatch):
    """Non-vacuity for the belt-and-suspenders assert: if a future edit ever
    stops deriving the class live, this must fail LOUDLY rather than write
    an unproducable class to disk."""
    monkeypatch.setattr(recorder_mod, "classify_screen", lambda *_a, **_kw: "not-a-real-class")
    rec = LoopRecorder("ore-run", ANCHOR_158)
    with pytest.raises(AssertionError):
        rec.step("P", PORT)


# ---------------------------------------------------------------------------
# Trap 2 -- wait_prompt is captured literally and escaped on write
# ---------------------------------------------------------------------------


def test_a_raw_unescaped_wait_prompt_can_fail_to_match_its_own_source_text():
    """The measured fact this module's docstring cites, executed here so it
    stays a fact rather than a claim: a live, metachar-heavy TW prompt
    compiles cleanly as a raw regex (the loader's compileability check
    cannot catch it) and then does not match the very text it came from.
    `[TL=00:00:00]` is a ONE-CHARACTER class over `{T,L,=,0,:}`, and the
    actual next character in the source text is a literal `[`, which is not
    a member of that class -- so the pattern fails at that position.
    """
    prompt_line = _text_and_prompt(ANCHOR_158_METACHAR)[1]
    raw_pattern = re.compile(prompt_line)  # compiles -- no loud failure
    assert raw_pattern.search(prompt_line) is None  # ...and silently never matches

    escaped_pattern = re.compile(re.escape(prompt_line))
    assert escaped_pattern.search(prompt_line) is not None


def test_confirm_exact_escapes_the_captured_prompt_never_stores_it_raw():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    step = rec.step("1", ANCHOR_158_METACHAR, confirm_exact=True)
    prompt_line = _text_and_prompt(ANCHOR_158_METACHAR)[1]

    assert step.wait_prompt == re.escape(prompt_line)
    assert step.wait_prompt != prompt_line  # never the raw text
    # Positive AND isolating: the escaped form self-matches...
    assert re.compile(step.wait_prompt).search(prompt_line) is not None
    # ...and does not spuriously match the shorter, unrelated prompt line
    # (specificity -- an over-widened escape would still "pass" the
    # self-match assertion above alone).
    assert re.compile(step.wait_prompt).search(_text_and_prompt(ANCHOR_158)[1]) is None


def test_confirm_exact_refuses_when_the_screen_has_no_prompt_line():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    with pytest.raises(RecorderError):
        rec.step("P", [], confirm_exact=True)


def test_an_empty_screen_step_without_confirm_exact_does_not_raise():
    """Isolates the cell above: the refusal is about `confirm_exact` PLUS a
    blank prompt line together, not about an empty screen in general."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    step = rec.step("P", [])
    assert step.expected_post_class == classify_screen("", "")
    assert step.wait_prompt is None


def test_the_escaped_wait_prompt_survives_a_real_save_and_load_round_trip(tmp_path):
    """Not the pure-`re` demonstration above -- the SAME fact, proven through
    a document actually written to disk and read back by the real loader."""
    rec = LoopRecorder("metachar-run", ANCHOR_158)
    rec.step("P", PORT)
    rec.step("1", ANCHOR_158_METACHAR, confirm_exact=True)
    rec.save(state_dir=tmp_path)

    loop = load_loop("metachar-run", state_dir=tmp_path)
    wait_prompt = loop.steps[1].wait_prompt
    metachar_prompt_line = _text_and_prompt(ANCHOR_158_METACHAR)[1]
    plain_prompt_line = _text_and_prompt(ANCHOR_158)[1]

    compiled = re.compile(wait_prompt)  # the loader already proved this compiles
    assert compiled.search(metachar_prompt_line) is not None  # self-match
    assert compiled.search(plain_prompt_line) is None  # specificity


# ---------------------------------------------------------------------------
# Parameterization (WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2)
# ---------------------------------------------------------------------------


def test_a_parameterized_step_writes_a_placeholder_not_the_literal():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    step = rec.step("50", PORT, param="qty")
    assert step.input == "{qty}"
    doc = rec.document()
    assert doc["params"] == {"qty": "50"}


def test_a_non_parameterized_step_still_writes_its_literal_input():
    """Isolates the cell above: opting IN on one step never generalizes a
    sibling step that did not ask for it."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("P", PORT)
    step = rec.step("50", PORT, param="qty")
    doc = rec.document()
    assert doc["steps"][0]["input"] == "P"
    assert doc["steps"][1]["input"] == "{qty}"
    assert step.input == "{qty}"


def test_document_omits_params_entirely_when_none_were_captured():
    """Byte-for-byte backward compatibility: a capture that never opts in
    produces the exact document shape it always did, no new key at all."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("P", PORT)
    doc = rec.document()
    assert "params" not in doc


def test_a_non_digit_keystrokes_cannot_be_parameterized():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    with pytest.raises(RecorderError):
        rec.step("P", PORT, param="qty")


def test_an_invalid_param_name_is_refused():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    for bad in ("1qty", "qty!", "", " ", "qty name"):
        with pytest.raises(RecorderError):
            rec.step("50", PORT, param=bad)


def test_reusing_a_param_name_with_the_same_literal_is_legal():
    """The same quantity demonstrated twice (e.g. two holds of the same
    count) is one parameter, not a conflict."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("50", PORT, param="qty")
    step2 = rec.step("50", ANCHOR_158_METACHAR, param="qty")
    assert step2.input == "{qty}"
    assert rec.document()["params"] == {"qty": "50"}


def test_reusing_a_param_name_with_a_different_literal_is_refused():
    """Two different literals under one name would mean the second
    silently overwrites the first's recorded default with no record
    either value existed -- refused rather than picking a winner."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("50", PORT, param="qty")
    with pytest.raises(RecorderError):
        rec.step("100", ANCHOR_158_METACHAR, param="qty")


def test_a_parameterized_loop_round_trips_through_the_loader_into_a_completed_replay(
    tmp_path,
):
    """The headline proof, extended: a captured placeholder loads with its
    recorded default AND replays by sending the resolved literal, never
    the placeholder text `{qty}`."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("50", PORT, param="qty")
    rec.save(state_dir=tmp_path)

    loop = load_loop("ore-run", state_dir=tmp_path)
    assert loop.params == {"qty": "50"}
    assert loop.steps[0].input == "{qty}"

    session = ScriptedSession(screens=[_text_and_prompt(ANCHOR_158), _text_and_prompt(PORT)])
    result = replay_loop(loop, session)

    assert result.outcome == OUTCOME_COMPLETED
    assert session.sends == [("50", None)]  # the resolved literal, never "{qty}"


# ---------------------------------------------------------------------------
# document() / save() plumbing
# ---------------------------------------------------------------------------


def test_document_raises_empty_recording_before_any_step():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    with pytest.raises(EmptyRecording):
        rec.document()


def test_save_raises_empty_recording_and_writes_nothing(tmp_path):
    rec = LoopRecorder("ore-run", ANCHOR_158)
    with pytest.raises(EmptyRecording):
        rec.save(state_dir=tmp_path)
    # Nothing was written -- the refusal happens before any filesystem call.
    assert not (tmp_path / "skills").exists()


def test_document_carries_the_exact_name_source_and_anchor():
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("P", PORT)
    doc = rec.document()

    assert doc["name"] == "ore-run"
    assert doc["source"] == "recorded"
    assert doc["start_anchor"] == 158
    assert doc["steps"] == [
        {"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"}
    ]
    assert doc["created_ts"].endswith("Z")


def test_save_defaults_to_blessed(tmp_path):
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("P", PORT)
    path = rec.save(state_dir=tmp_path)  # no `blessed=` -- proving the DEFAULT, not just True

    assert path == tmp_path / "skills" / "ore-run.json"
    loop = load_loop("ore-run", state_dir=tmp_path)
    assert loop.draft is False


def test_save_draft_writes_under_drafts_dirname_and_is_invisible_without_opt_in(tmp_path):
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("P", PORT)
    path = rec.save(blessed=False, state_dir=tmp_path)

    assert path == tmp_path / "skills" / "_drafts" / "ore-run.json"
    with pytest.raises(LoopNotFound):
        load_loop("ore-run", state_dir=tmp_path)  # opt-in required
    loop = load_loop("ore-run", state_dir=tmp_path, include_drafts=True)
    assert loop.draft is True


def test_saved_document_is_written_with_restrictive_permissions(tmp_path):
    rec = LoopRecorder("ore-run", ANCHOR_158)
    rec.step("P", PORT)
    path = rec.save(state_dir=tmp_path)
    assert (path.stat().st_mode & 0o777) == 0o600


# ---------------------------------------------------------------------------
# Trap 4 (dispatcher addendum) -- name is the identity; a MISS is never
# poisoned by a recording this module produced.
# ---------------------------------------------------------------------------


def test_save_sanitizes_the_filename_stem_but_keeps_the_name_field_verbatim(tmp_path):
    rec = LoopRecorder("ore run #1!", ANCHOR_158)
    rec.step("P", PORT)
    path = rec.save(state_dir=tmp_path)

    assert path.name != "ore run #1!.json"  # unsafe characters sanitized out of the FILENAME
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["name"] == "ore run #1!"  # ...but the identity field is verbatim

    # And the round trip is BY NAME, not by path -- proven by asking for the
    # exact name string, never the sanitized stem.
    loop = load_loop("ore run #1!", state_dir=tmp_path)
    assert loop.name == "ore run #1!"


def test_a_name_that_sanitizes_to_nothing_is_refused_at_save(tmp_path):
    rec = LoopRecorder("###", ANCHOR_158)
    rec.step("P", PORT)
    with pytest.raises(InvalidName):
        rec.save(state_dir=tmp_path)
    assert not (tmp_path / "skills").exists()


def test_a_recording_never_poisons_an_unrelated_miss_in_the_same_store(tmp_path):
    """Dispatcher addendum, measured against tip 470ed3c: a document with no
    usable `name` turns every future MISS in its directory into
    `LoopUnreadable` (the search could not be completed) rather than a clean
    `LoopNotFound`. This recorder cannot produce that shape -- every write
    carries a validated `name` -- so an unrelated lookup in the SAME store
    must still get the clean negative.
    """
    rec = LoopRecorder("alpha", ANCHOR_158)
    rec.step("P", PORT)
    rec.save(state_dir=tmp_path)

    assert load_loop("alpha", state_dir=tmp_path).name == "alpha"
    # A DIFFERENT, never-recorded name in the SAME store: a clean miss, not
    # "I could not tell".
    with pytest.raises(LoopNotFound):
        load_loop("zzz-never-recorded", state_dir=tmp_path)


def test_the_defective_shape_this_recorder_refuses_to_produce_really_would_poison_a_miss(tmp_path):
    """Not a test of `LoopRecorder` -- a test of WHY it validates `name` at
    all costs. Hand-writes the nameless document a broken writer could
    produce (the shape `_validate_name` makes unreachable through this
    module's own API) next to a real recording, and shows the poisoning it
    causes -- grounding the claim in this module's docstring by execution.
    """
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    rec = LoopRecorder("alpha", ANCHOR_158)
    rec.step("P", PORT)
    rec.save(state_dir=tmp_path)

    (skills / "nameless.json").write_text(
        json.dumps(
            {"steps": [{"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"}]}
        ),
        encoding="utf-8",
    )

    assert load_loop("alpha", state_dir=tmp_path).name == "alpha"  # the HIT survives
    with pytest.raises(LoopUnreadable):  # the MISS is poisoned
        load_loop("zzz-never-recorded", state_dir=tmp_path)


# ---------------------------------------------------------------------------
# THE headline proof -- record -> load -> replay to completion
# ---------------------------------------------------------------------------


def test_recorded_loop_round_trips_through_the_loader_into_a_completed_replay(tmp_path):
    """The strengthened Accept, in full: every one of the three(-plus-one)
    traps is exercised in a single capture, and the resulting document
    REPLAYS -- not merely loads."""
    rec = LoopRecorder("ore-run", ANCHOR_158)
    assert rec.start_anchor == 158
    rec.step("P", PORT)
    rec.step("1", ANCHOR_158_METACHAR, confirm_exact=True)
    path = rec.save(state_dir=tmp_path)
    assert path.exists()

    loop = load_loop("ore-run", state_dir=tmp_path)
    assert loop.name == "ore-run"
    assert loop.start_anchor == 158
    assert loop.draft is False
    assert loop.source == "recorded"
    assert [s.expected_post_class for s in loop.steps] == ["port_trade", "main_command"]
    assert loop.steps[0].wait_prompt is None
    metachar_prompt_line = _text_and_prompt(ANCHOR_158_METACHAR)[1]
    assert loop.steps[1].wait_prompt == re.escape(metachar_prompt_line)

    session = ScriptedSession(
        screens=[
            _text_and_prompt(ANCHOR_158),
            _text_and_prompt(PORT),
            _text_and_prompt(ANCHOR_158_METACHAR),
        ]
    )
    result = replay_loop(loop, session)

    assert result.outcome == OUTCOME_COMPLETED
    assert result.sends_issued == 2
    assert session.sends == [("P", None), ("1", re.escape(metachar_prompt_line))]


def test_a_draft_recording_also_round_trips_to_a_completed_replay(tmp_path):
    """The draft-vs-blessed design call does not change what X3 does with
    the document -- `player.py` never special-cases `Loop.draft`."""
    rec = LoopRecorder("ore-run-draft", ANCHOR_158)
    rec.step("P", PORT)
    rec.save(blessed=False, state_dir=tmp_path)

    loop = load_loop("ore-run-draft", state_dir=tmp_path, include_drafts=True)
    assert loop.draft is True

    session = ScriptedSession(screens=[_text_and_prompt(ANCHOR_158), _text_and_prompt(PORT)])
    result = replay_loop(loop, session)
    assert result.outcome == OUTCOME_COMPLETED


# ---------------------------------------------------------------------------
# Capture-only -- structural, not asserted
# ---------------------------------------------------------------------------


def test_the_recorder_still_cannot_send_a_keystroke():
    """The shared no-send scanner (`test_loop_loader.py`'s own instrument,
    already reused by `test_loop_player.py`), held to ZERO violations --
    unlike the player, this module has no send call site at all."""
    assert _send_violations(RECORDER_SRC, allow_session_modules=ALLOWED_SESSION_MODULES) == []


def test_the_no_send_scanner_would_still_catch_a_send_here():
    """Non-vacuity for the assertion above: a scanner that always answers
    `[]` proves nothing. Fed a real send call in the SAME waived import
    context this module runs under, it must still fire."""
    poisoned = RECORDER_SRC + "\n\ndef _cheat(session):\n    session.send_and_confirm('X', None)\n"
    assert _send_violations(poisoned, allow_session_modules=ALLOWED_SESSION_MODULES) != []


def test_the_recorder_only_imports_the_two_session_modules_player_is_also_waived_for():
    """The waiver is not open-ended: swap in a DIFFERENT session module and
    the scanner must still refuse it, even under the same call."""
    assert _send_violations(
        "from ..session.protocol import build_response", allow_session_modules=ALLOWED_SESSION_MODULES
    ) != []
