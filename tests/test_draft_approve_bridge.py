"""WO-DRAFT-APPROVE-KERNEL-BRIDGE — the cockpit's Analyze approval reaches
the kernel rule store, and reaches it only with human-supplied values.

Two claims, and the second is the one Max ruled on:

1. A bridged draft **round-trips** — stub → kernel document → `_drafts/` →
   `promote_draft` → `propose_macro` returns the macro. Before this WO an
   operator could press `y`, see the word "approved", and have nothing
   persist anywhere.
2. `rule_id`, `do` and `priority` are **never minted**. The teacher supplies
   the screen it observed; the human supplies what the rule is called, what it
   does, and how it ranks. A defaulted `priority` would be the worst of the
   three — every AI-authored rule would land at the same rank, and the kernel
   STOPs on a tie rather than guessing, so the default would convert a working
   proposal into `autopilot_ambiguous_rules`.

The round-trip is exercised on **real files through the real store**, not a
hand-built reply dict — the same standard #222's Accept 5 was held to, and for
the same reason: a fake reply asserts only that the test author can type the
expected string.
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap

import pytest

from tw2002_aiclient.cockpit.draft_approve import (
    DraftBridgeError,
    HUMAN_SUPPLIED_FIELDS,
    bridge_to_kernel_document,
    create_analyze_draft,
    promote_to_approved,
    screen_of,
)
from tw2002_aiclient.rule_engine import RuleDocumentError, rule_from_dict
from tw2002_aiclient.rules.reflex import propose_macro
from tw2002_aiclient.rules.store import drafts_dir, read_rule_store
from tw2002_aiclient.rules.writer import RuleWriteError, promote_draft, write_draft

HUMAN = {"rule_id": "dock-when-idle", "do": "dock", "priority": 10, "scope": "one-shot"}


# ---------------------------------------------------------------------------
# Accept 1 + 4 — the round trip, on real files
# ---------------------------------------------------------------------------


def test_an_analyze_proposal_becomes_a_rule_the_reflex_layer_can_select(tmp_path):
    """The whole WO in one test: press-y-and-nothing-happens is over.

    Every step is the real one. The stub comes from the cockpit's own
    `create_analyze_draft`, the document is written by `rules.writer`, blessed
    by `promote_draft`, and read back by `propose_macro` through the store —
    no doubles anywhere in the chain.
    """
    stub = create_analyze_draft("main_command")
    document = bridge_to_kernel_document(stub, **HUMAN)

    write_draft(document, state_dir=tmp_path)
    before = propose_macro("main_command", {}, state_dir=tmp_path)
    assert before.macro is None, "a draft must not fire"
    assert before.stop_reason.startswith("autopilot_no_candidates")

    promote_draft("dock-when-idle", state_dir=tmp_path)
    after = propose_macro("main_command", {}, state_dir=tmp_path)

    assert after.macro == "dock"
    assert after.rule_id == "dock-when-idle"
    assert after.stop_reason is None


def test_the_screen_the_teacher_observed_is_what_the_rule_matches(tmp_path):
    """The one field that crosses. If it did not, the rule would be blessed
    against the wrong screen — which fires correctly in a test that uses the
    same constant for both."""
    stub = create_analyze_draft("port_menu")
    write_draft(bridge_to_kernel_document(stub, **HUMAN), state_dir=tmp_path)
    promote_draft("dock-when-idle", state_dir=tmp_path)

    assert propose_macro("port_menu", {}, state_dir=tmp_path).macro == "dock"
    # ...and NOT for a different screen. Without this, `screen_match` could be
    # a constant and the test above would still pass.
    assert propose_macro("main_command", {}, state_dir=tmp_path).macro is None


def test_a_bridged_draft_is_inert_until_the_human_promotes_it(tmp_path):
    path = write_draft(bridge_to_kernel_document(create_analyze_draft("x"), **HUMAN),
                       state_dir=tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["approved"] is False

    report = read_rule_store(state_dir=tmp_path, include_drafts=True)
    assert report["rules"] == []
    assert [r.rule_id for r in report["drafts"]] == ["dock-when-idle"]


def _called_names(func) -> set:
    """Every function name *called* in `func`, by AST — not by text search.

    The first version of this guard grepped `inspect.getsource` for
    `"write_draft"` and failed on the bridge's own **docstring**, which names
    `rules.writer.write_draft` while explaining that it deliberately does not
    call it. A text scan cannot tell a citation from a call; that distinction
    is the entire question here.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    return {
        getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }


def test_the_bridge_itself_writes_nothing(tmp_path):
    """Pure translation. Persistence is `rules.writer`'s single job, and a
    second module that could write would make "what can create a rule" a
    survey again."""
    bridge_to_kernel_document(create_analyze_draft("main_command"), **HUMAN)
    assert not (tmp_path / "rules").exists()

    called = _called_names(bridge_to_kernel_document)
    forbidden = {"write_draft", "promote_draft", "open", "write_text",
                 "write_bytes", "replace", "mkstemp", "unlink"}
    assert not (called & forbidden), f"the bridge calls {called & forbidden}"


def test_that_no_write_guard_can_tell_a_call_from_a_mention():
    """Control, in both directions — the failure this guard already had once.

    A scanner that only proves it *fires* is half a control; the half that
    matters here is that a docstring naming `write_draft` does not count as
    calling it, because the bridge's docstring does exactly that.
    """
    def mentions_only():
        """This mentions write_draft and open( without calling either."""
        return {"note": "write_draft is not called here"}

    def actually_writes():
        write_draft({}, state_dir=None)

    assert "write_draft" not in _called_names(mentions_only)
    assert "write_draft" in _called_names(actually_writes)


# ---------------------------------------------------------------------------
# Accept 2 — no minted defaults, ever
# ---------------------------------------------------------------------------


def test_the_three_human_fields_have_no_defaults_in_the_signature():
    """Structural, and stronger than any runtime check.

    Omitting one is a `TypeError` raised by Python before a line of this
    module executes. A default value plus a validation branch could be argued
    away by a future caller in a hurry; an absent default cannot.
    """
    params = inspect.signature(bridge_to_kernel_document).parameters
    for field in HUMAN_SUPPLIED_FIELDS:
        assert params[field].default is inspect.Parameter.empty, (
            f"{field} grew a default — Max's ruling forbids minting it"
        )
        assert params[field].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        bridge_to_kernel_document(create_analyze_draft("x"), rule_id="r", do="d")


@pytest.mark.parametrize("field", HUMAN_SUPPLIED_FIELDS)
def test_a_missing_human_field_refuses_and_names_itself(field, tmp_path):
    kwargs = {**HUMAN, field: None}
    with pytest.raises(DraftBridgeError, match=field):
        bridge_to_kernel_document(create_analyze_draft("main_command"), **kwargs)
    assert not drafts_dir(tmp_path).exists()


@pytest.mark.parametrize("field", ["rule_id", "do"])
def test_a_whitespace_only_value_is_refused_and_the_parser_would_not_have_caught_it(field):
    """The genuinely load-bearing part of the bridge's own check.

    Measured against the parser rather than assumed: `rule_from_dict` refuses
    `None` and `""` for all three fields on its own, so this branch adds
    exactly one thing — a **whitespace-only** `rule_id` or `do`, which is a
    non-empty string the parser happily admits. A rule named `"   "` would be
    born, and `safe_stem` would then refuse to give it a filename.

    The precondition assert is what keeps this test honest: if the kernel ever
    tightens to reject whitespace, this goes red and says the bridge's check
    has become decoration.
    """
    admitted = rule_from_dict({"rule_id": "r", "screen_match": "s", "do": "d",
                               "priority": 1, **{field: "   "}})
    assert getattr(admitted, field) == "   ", (
        "precondition: the kernel admits whitespace-only, so this branch is reachable"
    )

    with pytest.raises(DraftBridgeError, match=field):
        bridge_to_kernel_document(create_analyze_draft("main_command"),
                                  **{**HUMAN, field: "   "})


@pytest.mark.parametrize("field", HUMAN_SUPPLIED_FIELDS)
@pytest.mark.parametrize("bad", [None, ""])
def test_the_kernel_is_the_layer_that_catches_none_and_empty(field, bad):
    """Disclosure, not coverage: these cases are refused by BOTH layers.

    The bridge's own branch is not what makes them safe — the parser refuses
    them independently. Pinning that here means nobody later reads the
    bridge's check as the thing protecting these values, and if the bridge's
    branch is deleted this test still passes, correctly.
    """
    with pytest.raises(RuleDocumentError):
        rule_from_dict({"rule_id": "r", "screen_match": "s", "do": "d",
                        "priority": 1, **{field: bad}})


def test_the_refusal_cases_are_not_vacuous(tmp_path):
    """Control: the same call with all three supplied must succeed, or every
    refusal above could be passing for an unrelated reason."""
    document = bridge_to_kernel_document(create_analyze_draft("main_command"), **HUMAN)
    assert rule_from_dict(document).priority == 10


def test_a_stub_with_no_screen_class_is_refused(tmp_path):
    """`create_stub` degrades a hostile screen class to `""`. A rule with
    nothing to match on is not a rule, and inventing a screen would be the
    same sin as inventing a priority."""
    blind = create_analyze_draft(None)
    assert screen_of(blind) == "", "precondition: the stub really is screenless"
    with pytest.raises(DraftBridgeError, match="screen"):
        bridge_to_kernel_document(blind, **HUMAN)


def test_the_bridge_cannot_be_asked_to_approve():
    """Same shape as `write_draft`: the guarantee is an absent parameter."""
    params = set(inspect.signature(bridge_to_kernel_document).parameters)
    assert "approved" not in params
    with pytest.raises(TypeError):
        bridge_to_kernel_document(create_analyze_draft("x"), **HUMAN, approved=True)

    document = bridge_to_kernel_document(create_analyze_draft("x"), **HUMAN)
    assert document["approved"] is False


def test_the_bridge_does_not_launder_the_cockpits_own_approved_flag(tmp_path):
    """`promote_to_approved` sets `approved: True` on the in-memory stub. That
    flag is cockpit bookkeeping, not the kernel's approval, and the bridge
    must not carry it across — otherwise pressing `y` first would bless a rule
    without anyone typing `tw rule approve`."""
    approved_stub = promote_to_approved(create_analyze_draft("main_command"))
    document = bridge_to_kernel_document(approved_stub, **HUMAN)

    assert document["approved"] is False
    path = write_draft(document, state_dir=tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["approved"] is False
    assert read_rule_store(state_dir=tmp_path)["rules"] == [], "nothing was blessed"


# ---------------------------------------------------------------------------
# Accept 3 — the untranslated stub stays out
# ---------------------------------------------------------------------------


def test_the_raw_stub_still_cannot_reach_the_store(tmp_path):
    stub = create_analyze_draft("main_command")
    with pytest.raises(RuleDocumentError):
        rule_from_dict(stub)
    with pytest.raises(RuleWriteError):
        write_draft(stub, state_dir=tmp_path)
    assert not drafts_dir(tmp_path).exists()


# ---------------------------------------------------------------------------
# The operator-facing half (ruling A)
# ---------------------------------------------------------------------------


def _run_play_calls() -> set:
    """Names called inside `app._run_play`, the curses loop that owns the gate."""
    from pathlib import Path

    import tw2002_aiclient.app as app_mod

    tree = ast.parse(Path(app_mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_play":
            return {
                getattr(c.func, "attr", None) or getattr(c.func, "id", None)
                for c in ast.walk(node)
                if isinstance(c, ast.Call)
            }
    raise AssertionError("app._run_play not found — this guard is aimed at nothing")


def test_the_cockpit_gate_is_actually_wired_to_the_bridge_hint():
    """Wiring pin. Play now collects identity then blesses via the writer.

    Historically this asserted ``compose_bridge_command`` (CLI-only path).
    WO-PLAY-RULE-IDENTITY replaced that with typed entry + write/promote;
    the CLI composer has since been retired (WO-CLEANUP-COMPOSE-BRIDGE-
    COMMAND-UNREACHABLE) as it never gained a caller outside its own tests.
    """
    called = _run_play_calls()
    assert "bridge_to_kernel_document" in called, (
        "the identity-complete branch no longer bridges the analyze stub"
    )
    assert "write_draft" in called and "promote_draft" in called
    assert "begin_rule_identity" in called
    # Control: the scan is discriminating, not a set that contains everything.
    assert "compose_bridge_command_that_does_not_exist" not in called


def _emittable_strings(module) -> list:
    """Every string literal in *module* — what the program can actually say.

    Deliberately NOT a text search. The first version of this guard grepped
    the file and failed on the comment three lines above the fix, which quotes
    the old wording to explain why it was removed. A comment cannot reach an
    operator's screen; a string literal can, and that is the whole claim being
    made. Comments are absent from the AST by construction, so parsing asks
    the exact question instead of one that merely correlates with it.
    """
    from pathlib import Path

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def test_the_false_playback_eligible_claim_can_no_longer_be_emitted():
    """The claim the kernel-bridge WO existed to kill — still dead.

    `y` used to report "analyze draft approved (playback-eligible stub)" while
    persisting nowhere. Play now blesses via typed identity; the honest success
    line names the rule and points at `V`. The old CLI-only "not yet a rule"
    claim is gone from Play's emit path.
    """
    import tw2002_aiclient.app as app_mod

    said = _emittable_strings(app_mod)
    assert not [s for s in said if "playback-eligible" in s]
    assert not [s for s in said if "analyze_rule_approved" in s]
    assert not [s for s in said if "not yet a rule" in s]

    assert any(s == "analyze_rule_written" for s in said)
    assert any("rule identity cancelled" in s for s in said)


def test_that_claim_guard_reads_literals_rather_than_comments(tmp_path):
    """Control for the guard above, in the direction that already bit once."""
    planted = tmp_path / "m.py"
    planted.write_text(
        '# playback-eligible stub — quoted in a comment, not emittable\n'
        'GOOD = "not yet a rule"\n'
    )

    class _Fake:
        __file__ = str(planted)

    said = _emittable_strings(_Fake)
    assert not [s for s in said if "playback-eligible" in s], (
        "the guard counted a comment as something the program can say"
    )
    assert "not yet a rule" in said


