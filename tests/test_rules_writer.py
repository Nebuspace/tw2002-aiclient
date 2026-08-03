"""WO-RULE-WRITER-DRAFTS -- the AI author can propose a rule and can never
approve one.

The property under test is not "drafts are written correctly". It is that
**every path from a written draft to a firing macro passes through a human**,
and that the code makes the alternative inexpressible rather than merely
discouraged. Canon: *"every rule is human-approved before it can fire"*.

Three separable claims, each pinned here on real files rather than on the
writer's return value:

1. ``write_draft`` cannot produce ``approved: true`` -- no parameter asks for
   it, and a document arriving with it is refused rather than downgraded.
2. A written draft is **invisible** to the selector: the blessed store does
   not list it and ``propose_macro`` answers ``autopilot_no_candidates``.
3. ``promote_draft`` is the sole crossing, and it is reached only from an
   explicit operator command.

Several tests below inject the defect and assert the suite notices, because a
green suite over a hard-coded ``False`` is exactly as green as a green suite
over a hard-coded ``True`` -- the constant is invisible to a test that only
reads what the writer just wrote.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tw2002_aiclient.rule_engine import RuleDocumentError, rule_from_dict
from tw2002_aiclient.rules import store as store_mod
from tw2002_aiclient.rules import writer as writer_mod
from tw2002_aiclient.rules.reflex import propose_macro
from tw2002_aiclient.rules.store import (
    STATUS_OK,
    STATUS_PARTIAL,
    drafts_dir,
    read_rule_store,
    resolve_roots,
)
from tw2002_aiclient.rules.writer import (
    RuleWriteError,
    promote_draft,
    safe_stem,
    write_draft,
)

DRAFT = {
    "rule_id": "dock-when-idle",
    "screen_match": "command_prompt",
    "do": "dock",
    "priority": 10,
}


# ---------------------------------------------------------------------------
# 1. The writer cannot bless
# ---------------------------------------------------------------------------


def test_a_written_draft_is_inert_on_disk(tmp_path):
    """The bytes an operator would `cat`, not the object the writer returned."""
    path = write_draft(DRAFT, state_dir=tmp_path)
    on_disk = json.loads(path.read_text(encoding="utf-8"))

    assert on_disk["approved"] is False
    assert on_disk["rule_id"] == "dock-when-idle"
    assert path.parent == drafts_dir(tmp_path)


def test_write_draft_offers_no_way_to_ask_for_approval():
    """Structural: the guarantee is the *absence* of a parameter.

    A refusal inside the body can be argued around by the next caller; a
    keyword that does not exist cannot be passed. This pins the shape of the
    promise, so re-introducing an `approved=` knob is a visible test edit
    rather than a quiet signature change.
    """
    import inspect

    params = set(inspect.signature(write_draft).parameters)
    assert "approved" not in params
    assert params == {"document", "state_dir", "rules_path", "drafts_path", "world_id"}

    with pytest.raises(TypeError):
        write_draft(DRAFT, approved=True)  # type: ignore[call-arg]


def test_a_document_claiming_approval_is_refused_not_downgraded(tmp_path):
    """Refusing says so; downgrading lets the author believe it blessed one.

    Silently writing `false` over the caller's `true` would leave an AI author
    with a successful return value and a belief that a rule is live. The
    refusal is the only outcome that transfers that information back.
    """
    with pytest.raises(RuleWriteError, match="approved: true"):
        write_draft({**DRAFT, "approved": True}, state_dir=tmp_path)

    assert list(drafts_dir(tmp_path).glob("*.json")) == [] or not drafts_dir(tmp_path).exists()


def test_the_inertness_pin_is_not_vacuous(tmp_path, monkeypatch):
    """Control: force the writer to bless and confirm this file notices.

    Without this, every assertion above is satisfied by a writer that hard-codes
    `True` just as happily as one that hard-codes `False` -- they only ever
    compare the file against what the writer chose to put in it. Patching the
    round-tripper is the smallest injection that reaches the written bytes.
    """
    real = writer_mod.rule_to_dict

    def blessing(rule):
        out = real(rule)
        out["approved"] = True
        return out

    monkeypatch.setattr(writer_mod, "rule_to_dict", blessing)
    path = write_draft(DRAFT, state_dir=tmp_path)

    # The belt-and-braces line in `write_draft` re-stamps False AFTER the
    # round-trip, so this injection is caught. If that line is ever deleted,
    # this assertion flips and says exactly which guarantee went with it.
    assert json.loads(path.read_text(encoding="utf-8"))["approved"] is False, (
        "a patched round-tripper reached the disk with approved: true -- "
        "the post-round-trip re-stamp in write_draft is what prevents this"
    )


def test_a_malformed_draft_leaves_nothing_on_disk(tmp_path):
    """Validated through the kernel parser BEFORE the write, not after.

    A draft that cannot load is a file an operator will meet later as
    "unreadable", at a moment when they no longer remember writing it.
    """
    with pytest.raises(RuleWriteError):
        write_draft({**DRAFT, "priority": "high"}, state_dir=tmp_path)
    with pytest.raises(RuleWriteError):
        write_draft({**DRAFT, "unknown_field": 1}, state_dir=tmp_path)
    with pytest.raises(RuleWriteError, match="mapping"):
        write_draft(["not", "a", "mapping"], state_dir=tmp_path)  # type: ignore[arg-type]

    assert not drafts_dir(tmp_path).exists() or list(drafts_dir(tmp_path).iterdir()) == []


def test_the_writer_routes_through_the_kernel_parser(tmp_path, monkeypatch):
    """Executed proof of parser unity on the WRITE side.

    `tests/test_rules_store.py` proves the reader admits only through
    `rule_from_dict`. A writer with its own lenient validation would put
    documents on disk that the reader then refuses -- the two halves have to
    agree, and the only way to guarantee that is to share the parser.
    """
    seen = []

    def spy(payload):
        seen.append(payload)
        raise RuleDocumentError("refused by the spy")

    monkeypatch.setattr(writer_mod, "rule_from_dict", spy)
    with pytest.raises(RuleWriteError, match="refused by the spy"):
        write_draft(DRAFT, state_dir=tmp_path)

    assert seen and seen[0]["approved"] is False, (
        "the writer did not route this document through rule_from_dict"
    )


# ---------------------------------------------------------------------------
# 2. A draft is invisible to the thing that decides
# ---------------------------------------------------------------------------


def test_a_draft_is_absent_from_the_blessed_store(tmp_path):
    write_draft(DRAFT, state_dir=tmp_path)
    report = read_rule_store(state_dir=tmp_path)

    assert report["rules"] == []
    assert report["drafts"] == []
    assert report["include_drafts"] is False
    # `ok`, not `unreadable` -- we looked and found no blessed rule. A
    # draft-only install is a completed search, not a blind one.
    assert report["status"] == STATUS_OK


def test_a_draft_only_install_stops_rather_than_firing(tmp_path):
    """The end-to-end claim, through the layer the app would actually call.

    Every intermediate assertion in this file is satisfiable by a store that
    hides drafts and a `propose_macro` that reads a different store. This one
    is not.
    """
    write_draft(DRAFT, state_dir=tmp_path)
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert decision.macro is None
    assert decision.fired is False
    assert decision.stop_reason.startswith("autopilot_no_candidates")


def test_include_drafts_surfaces_them_in_their_own_list_never_in_rules(tmp_path):
    """Two lists, not one list with a `draft: True` flag.

    `loops/store.py` uses the flag shape because its consumer is a listing. The
    consumer here is a *selector*, and a flag on a row is safe only while every
    reader remembers to check it -- forgetting is silent, and the thing that
    would be forgotten is whether the app is allowed to act.
    """
    write_draft(DRAFT, state_dir=tmp_path)
    report = read_rule_store(state_dir=tmp_path, include_drafts=True)

    assert [r.rule_id for r in report["drafts"]] == ["dock-when-idle"]
    assert report["rules"] == []
    assert all(r.approved is False for r in report["drafts"])


def test_reflex_never_asks_for_drafts():
    """The default is the safety property; pin it at the call site.

    `include_drafts` defaulting to False protects nothing if the one caller
    that matters overrides it. A structural check because a behavioural one
    passes on an install that happens to have no drafts.
    """
    source = Path(writer_mod.__file__).parent / "reflex.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    passed = [
        kw.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "include_drafts"
    ]
    assert passed == [], (
        "rules/reflex.py passes include_drafts explicitly; the selector must "
        "stay on the default so a draft can never enter selection"
    )


def test_a_draft_directory_file_claiming_approval_is_refused(tmp_path):
    """A hand-edit, or a second author. Loud, because the writer cannot do it.

    The store refuses rather than coercing to False for the same reason the
    writer refuses rather than downgrading: coercion "repairs" the file and
    destroys the evidence that something wrote `approved: true` into a
    directory that may not contain it.
    """
    drafts = drafts_dir(tmp_path)
    drafts.mkdir(parents=True)
    (drafts / "sneaky.json").write_text(json.dumps({**DRAFT, "approved": True}))

    report = read_rule_store(state_dir=tmp_path, include_drafts=True)

    assert report["drafts"] == []
    assert report["status"] == STATUS_PARTIAL
    assert "approved: true" in report["unreadable"][0]["reason"]


def test_that_refusal_is_not_vacuous(tmp_path):
    """The same file with `approved: false` must load, or the test above
    proves only that the draft directory is unreadable in general."""
    drafts = drafts_dir(tmp_path)
    drafts.mkdir(parents=True)
    (drafts / "sneaky.json").write_text(json.dumps({**DRAFT, "approved": False}))

    report = read_rule_store(state_dir=tmp_path, include_drafts=True)
    assert [r.rule_id for r in report["drafts"]] == ["dock-when-idle"]
    assert report["status"] == STATUS_OK


# ---------------------------------------------------------------------------
# 3. Promotion is the sole crossing
# ---------------------------------------------------------------------------


def test_promotion_moves_a_draft_into_the_blessed_library(tmp_path):
    write_draft(DRAFT, state_dir=tmp_path)
    dest = promote_draft("dock-when-idle", state_dir=tmp_path)

    assert json.loads(dest.read_text(encoding="utf-8"))["approved"] is True
    report = read_rule_store(state_dir=tmp_path, include_drafts=True)
    assert [r.rule_id for r in report["rules"]] == ["dock-when-idle"]
    assert report["drafts"] == [], "the draft outlived its promotion"


def test_a_promoted_rule_is_what_finally_lets_the_app_act(tmp_path):
    """The whole point, stated once: before a human, STOP; after, a macro."""
    write_draft(DRAFT, state_dir=tmp_path)
    before = propose_macro("command_prompt", {}, state_dir=tmp_path)
    promote_draft("dock-when-idle", state_dir=tmp_path)
    after = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert before.macro is None and before.stop_reason.startswith("autopilot_no_candidates")
    assert after.macro == "dock"
    assert after.rule_id == "dock-when-idle"


def test_promotion_revalidates_because_a_draft_can_be_hand_edited(tmp_path):
    """Drafts sit on disk between writing and approving. That gap is exactly
    when a malformed one appears, and approving is the last cheap refusal."""
    path = write_draft(DRAFT, state_dir=tmp_path)
    path.write_text(json.dumps({**DRAFT, "priority": "high"}))

    with pytest.raises(RuleWriteError, match="not promotable"):
        promote_draft("dock-when-idle", state_dir=tmp_path)
    assert read_rule_store(state_dir=tmp_path)["rules"] == []


def test_promoting_a_draft_that_does_not_exist_is_a_named_refusal(tmp_path):
    with pytest.raises(RuleWriteError, match="no draft named"):
        promote_draft("never-written", state_dir=tmp_path)


def test_writer_is_the_only_module_in_the_package_that_writes(tmp_path):
    """Structural: one writer, so "what can create a rule" has one answer.

    Sibling of the store's `Rule(...)` bypass guard. A second writer would not
    announce itself either -- it would look like a convenience helper on the
    reader, and it would not be routed through the parser or the approval
    split.
    """
    package = Path(store_mod.__file__).parent
    offenders = _write_calls_outside(package, allowed={"writer.py", "migrate.py"})
    assert offenders == [], (
        f"{offenders} write to disk; rules/writer.py is the only sanctioned "
        f"writer in this package"
    )


#: Module-level write APIs, matched on the **qualified** name.
_QUALIFIED_WRITES = {
    "os.replace", "os.rename", "os.unlink", "os.remove", "os.rmdir", "os.mkdir",
    "os.makedirs", "os.truncate", "os.fdopen",
    "shutil.rmtree", "shutil.move", "shutil.copy", "shutil.copy2",
    "tempfile.mkstemp", "tempfile.NamedTemporaryFile",
}

#: Bare attribute names with no common read-only meaning, so a receiver we
#: cannot resolve is still safe to flag.
_BARE_WRITES = {"write_text", "write_bytes", "touch", "unlink", "mkdir", "rmdir"}

# `replace` and `rename` are deliberately NOT in `_BARE_WRITES`, though
# `Path.replace` is a real write. `str.replace` is far more common -- it is
# what `cli.py` uses to turn a field name into a flag -- and this scanner
# cannot tell the two apart without type inference. A guard that fires on
# every string manipulation in the package gets deleted by the third person
# who trips over it, and a deleted guard catches nothing at all. The stated
# limit: a bare `p.replace(q)` on a Path would be missed here. `os.replace`,
# which is what an atomic write actually uses, is caught above.


def _dotted(func: ast.expr) -> str:
    """`os.replace` for `os.replace(...)`; the bare attr otherwise."""
    parts = []
    node = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _write_calls_outside(package: Path, *, allowed: str | set[str]) -> list[str]:
    """Every disk-mutating call in the package outside the allowed module(s)."""
    allowed_names = {allowed} if isinstance(allowed, str) else set(allowed)
    found = []
    for path in sorted(package.glob("*.py")):
        if path.name in allowed_names:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            bare = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if dotted in _QUALIFIED_WRITES or bare in _BARE_WRITES:
                found.append(f"{path.name}:{node.lineno}")
            elif bare == "open":
                # `open(p)` is a read; only a mode argument makes it a write.
                modes = [a for a in node.args[1:] if isinstance(a, ast.Constant)]
                modes += [k.value for k in node.keywords if k.arg == "mode"]
                if any(isinstance(m, ast.Constant) and set("wax+") & set(str(m.value)) for m in modes):
                    found.append(f"{path.name}:{node.lineno}")
    return found


def test_the_single_writer_guard_can_detect_a_second_writer(tmp_path):
    """Control. A scanner that matched nothing would pass on every package."""
    (tmp_path / "writer.py").write_text("import os\nos.replace('a', 'b')\n")
    (tmp_path / "sneaky.py").write_text("from pathlib import Path\nPath('x').write_text('y')\n")
    (tmp_path / "opener.py").write_text("f = open('x', 'w')\n")
    (tmp_path / "renamer.py").write_text("import os\nos.replace('a', 'b')\n")

    found = _write_calls_outside(tmp_path, allowed="writer.py")
    assert found == ["opener.py:1", "renamer.py:2", "sneaky.py:2"], found


def test_the_single_writer_guard_does_not_fire_on_string_manipulation(tmp_path):
    """The other half of the control, and the reason this scanner was rewritten.

    The first version matched bare attribute names, so `f.replace("_", "-")`
    in `rules/cli.py` -- building a flag name out of a field name -- was
    reported as a disk write. That false positive is the failure mode that
    gets a guard deleted rather than fixed, so it is pinned here as a
    requirement: reads and string work must stay silent.
    """
    (tmp_path / "writer.py").write_text("x = 1\n")
    (tmp_path / "strings.py").write_text(
        'a = "x_y".replace("_", "-")\n'
        'b = [s.replace("a", "b") for s in ("c",)]\n'
        'c = "A".rename if False else None\n'
    )
    (tmp_path / "reader.py").write_text(
        "from pathlib import Path\n"
        "f = open('x')\n"
        "g = open('x', encoding='utf-8')\n"
        "h = Path('x').read_text()\n"
        "i = open('x', 'r')\n"
    )

    assert _write_calls_outside(tmp_path, allowed="writer.py") == []


# ---------------------------------------------------------------------------
# Filenames are not identities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule_id, stem",
    [
        ("../../etc/passwd", "etc-passwd"),
        ("/absolute/thing", "absolute-thing"),
        (".hidden", "hidden"),
        ("spaces and punctuation!", "spaces-and-punctuation"),
    ],
)
def test_a_rule_id_cannot_escape_the_store_directory(rule_id, stem, tmp_path):
    """A rule_id is operator-supplied and becomes a filename. This is the
    boundary where traversal and hidden files stop being possible."""
    assert safe_stem(rule_id) == stem
    path = write_draft({**DRAFT, "rule_id": rule_id}, state_dir=tmp_path)
    assert path.parent == drafts_dir(tmp_path)
    assert path.name == f"{stem}.json"
    # The document keeps its real identity; only the filename is sanitised.
    assert json.loads(path.read_text(encoding="utf-8"))["rule_id"] == rule_id


def test_a_rule_id_with_no_safe_form_is_refused_rather_than_defaulted(tmp_path):
    """Inventing a stem would put the document somewhere its author cannot
    predict, and the author is the one who has to find it again."""
    with pytest.raises(RuleWriteError, match="no filesystem-safe form"):
        write_draft({**DRAFT, "rule_id": "..."}, state_dir=tmp_path)


def test_two_drafts_sharing_a_stem_refuse_rather_than_overwrite(tmp_path):
    """`safe_stem` is lossy, so distinct ids can collide on one filename.

    Pinned separately from the promote path below. An earlier version of this
    test wrote both calls inside one `pytest.raises` block, which made it
    impossible to say which of the two guards had fired -- and in fact only
    the promote-side one ever did, so deleting the draft-side call survived a
    mutation pass with the suite green.
    """
    write_draft(DRAFT, state_dir=tmp_path)
    with pytest.raises(RuleWriteError, match="already holds"):
        write_draft({**DRAFT, "rule_id": "dock/when/idle"}, state_dir=tmp_path)

    surviving = read_rule_store(state_dir=tmp_path, include_drafts=True)["drafts"]
    assert [r.rule_id for r in surviving] == ["dock-when-idle"]


def test_promoting_onto_another_rules_filename_refuses(tmp_path):
    """The blessed-side half. This is the one that would delete a rule a human
    approved, surfacing later only as a reflex that stopped existing."""
    write_draft(DRAFT, state_dir=tmp_path)
    promote_draft("dock-when-idle", state_dir=tmp_path)

    write_draft({**DRAFT, "rule_id": "dock/when/idle"}, state_dir=tmp_path)
    with pytest.raises(RuleWriteError, match="already holds"):
        promote_draft("dock/when/idle", state_dir=tmp_path)

    survivors = read_rule_store(state_dir=tmp_path)["rules"]
    assert [r.rule_id for r in survivors] == ["dock-when-idle"]


def test_rewriting_the_same_rule_id_is_an_update_not_a_collision(tmp_path):
    """Control for the guard above -- it must not block legitimate edits."""
    write_draft(DRAFT, state_dir=tmp_path)
    path = write_draft({**DRAFT, "do": "twarp"}, state_dir=tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["do"] == "twarp"


def test_a_failed_write_leaves_no_temporary_file_behind(tmp_path, monkeypatch):
    """Atomic write, and no debris. A `.tmp-*` file is skipped by today's
    `.json` filter, which makes the cleanup correct by a coincidence in
    another module rather than by this one."""
    import os as os_mod

    def boom(src, dst):
        raise OSError("no space left on device")

    monkeypatch.setattr(writer_mod.os, "replace", boom)
    with pytest.raises(OSError):
        write_draft(DRAFT, state_dir=tmp_path)

    assert list(drafts_dir(tmp_path).iterdir()) == [], "temporary file survived a failed write"
    assert os_mod is not None  # keep the import meaningful under -O


# ---------------------------------------------------------------------------
# One resolution of the two roots -- regression pin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"state_dir": "STATE"},
        {"rules_path": "RULES"},
        {"rules_path": "RULES", "drafts_path": "DRAFTS"},
        {"state_dir": "STATE", "rules_path": "RULES"},
    ],
)
def test_reader_and_writer_resolve_the_same_drafts_directory(kwargs, tmp_path):
    """Regression pin, found during this build.

    The reader derived `drafts` from `rules_path`; the writer derived it from
    `state_dir` and ignored `rules_path` entirely. Passing `rules_path=tmp_path`
    alone -- the most natural thing a test does -- sent the writer to the
    operator's REAL `state/rules/_drafts`, where `promote_draft` would have
    blessed and then deleted live drafts.

    Both now call `resolve_roots`. This asserts they agree for every override
    combination rather than for the one the last author happened to try.
    """
    resolved = {k: str(tmp_path / v) for k, v in kwargs.items()}
    blessed, drafts = resolve_roots(**resolved)

    report = read_rule_store(include_drafts=True, **resolved)
    assert report["roots"][0]["path"] == str(blessed)
    assert report["roots"][1]["path"] == str(drafts)

    written = write_draft(DRAFT, **resolved)
    assert written.parent == drafts, (
        f"writer wrote to {written.parent}, reader looks in {drafts}"
    )
    assert read_rule_store(include_drafts=True, **resolved)["drafts"][0].rule_id == "dock-when-idle"


def test_resolve_roots_is_pure_path_math(tmp_path):
    blessed, drafts = resolve_roots(state_dir=tmp_path)
    assert (blessed, drafts) == (tmp_path / "rules", tmp_path / "rules" / "_drafts")
    assert not blessed.exists()


# ---------------------------------------------------------------------------
# The reconciled boundary -- was a gap marker, now a pair of pins
# ---------------------------------------------------------------------------
#
# WO-DRAFT-APPROVE-KERNEL-BRIDGE (2026-07-29) closed the gap that
# `test_the_cockpit_analyze_draft_cannot_enter_the_rule_store` used to mark.
# That test was written to go RED the day the schemas were reconciled, and it
# did. It is replaced below rather than deleted, because both halves of what
# it asserted still matter: the bridged shape must round-trip, AND the raw
# stub must still be refused. Losing the second half is how a bridge quietly
# becomes a bypass.


def test_the_bridged_analyze_draft_round_trips_into_the_rule_store(tmp_path):
    """The reconcile, proven end to end on real files.

    `cockpit/draft_approve.bridge_to_kernel_document` is the one crossing
    between the cockpit's stub vocabulary and the kernel's rule schema. What
    the teacher observed (the screen class) crosses; what only a human can
    decide (`rule_id`, `do`, `priority`) is supplied here as an argument,
    because Max ruled no value of those three may ever be minted.
    """
    from tw2002_aiclient.cockpit.draft_approve import (
        bridge_to_kernel_document,
        create_analyze_draft,
    )

    stub = create_analyze_draft("command_prompt")
    document = bridge_to_kernel_document(
        stub, rule_id="dock-when-idle", do="dock", priority=10, scope="one-shot"
    )

    # Crossed, and inert on arrival.
    assert document["screen_match"] == "command_prompt"
    assert document["approved"] is False
    rule = rule_from_dict(document)          # THE parser admits it
    assert rule.rule_id == "dock-when-idle"

    path = write_draft(document, state_dir=tmp_path)
    assert path.parent == drafts_dir(tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["approved"] is False

    # Still not blessed by writing it -- the human act is separate.
    assert read_rule_store(state_dir=tmp_path)["rules"] == []


def test_the_raw_stub_still_cannot_bless_itself(tmp_path):
    """Retained half of the old tripwire, and the reason it is retained.

    The bridge exists so a *translated* stub can enter the store. It must not
    make the *untranslated* one admissible: the raw shape has no `rule_id` and
    no `priority`, so admitting it would mean inventing both -- the precise
    thing the ruling forbids. `promote_to_approved` setting its own
    `approved: True` flag makes this sharper, not softer: that flag is the
    cockpit's in-memory bookkeeping and must never be mistaken by the store
    for the kernel's approval.
    """
    from tw2002_aiclient.cockpit.draft_approve import create_analyze_draft, promote_to_approved

    stub = create_analyze_draft("command_prompt")
    with pytest.raises(RuleDocumentError):
        rule_from_dict(stub)
    with pytest.raises(RuleWriteError):
        write_draft(stub, state_dir=tmp_path)

    approved = promote_to_approved(stub)
    assert approved["approved"] is True, "precondition: the cockpit did set its own flag"
    with pytest.raises(RuleDocumentError):
        rule_from_dict(approved)
    with pytest.raises(RuleWriteError):
        write_draft(approved, state_dir=tmp_path)

    assert not drafts_dir(tmp_path).exists() or list(drafts_dir(tmp_path).iterdir()) == []
