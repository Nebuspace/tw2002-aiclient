"""WO-GUARDED-RULE-KERNEL — the reflex layer's truth table, with its controls.

Canon: `canon/architecture/rule-macro-engine.md`.

Each Accept clause gets a positive test AND a control that fails if the guard it
depends on is removed. The controls exist because most of this module's value is
in what it REFUSES to do, and a refusal is the easiest behaviour in the world to
test vacuously: a decision with no macro looks identical whether it was reached
by the safety rule under test or by the document simply not matching anything.
So every negative assertion below is paired with a positive showing the same
document DOES fire once the one thing being tested is corrected.
"""

from __future__ import annotations

import itertools

import pytest

from tw2002_aiclient.rule_engine import (
    GUARD_OPERATORS,
    STOP_AMBIGUOUS,
    STOP_NO_CANDIDATES,
    UNKNOWN,
    Guard,
    Rule,
    RuleDocumentError,
    document_from_dicts,
    document_to_dicts,
    rule_from_dict,
    select_rule,
)


def _rule(rule_id="r1", *, screen="port_trade", do="macro_a", priority=10,
          approved=True, guards=()):
    return Rule(rule_id=rule_id, screen_match=screen, do=do, priority=priority,
                approved=approved, guards=tuple(guards))


def _stop_guard(fact="credits", reason="credits_stale"):
    return Guard(fact=fact, op="is_false", posture="stop", stop_reason=reason)


# ── Accept 1 — the happy path ───────────────────────────────────────────────


def test_approved_matching_rule_with_passing_guards_selects_its_macro():
    rule = _rule(guards=[Guard(fact="credits", op="ge", value=100)])
    decision = select_rule("port_trade", [rule], {"credits": 500})
    assert decision.macro == "macro_a"
    assert decision.rule_id == "r1"
    assert decision.stop_reason is None
    assert decision.fired is True


def test_a_decision_never_carries_both_a_macro_and_a_stop():
    """The outcome is exclusive by construction; pin it across every branch."""
    rules = [
        _rule("fires"),
        _rule("stops", guards=[_stop_guard()]),
        _rule("draft", approved=False),
    ]
    for screen, facts in (("port_trade", {"credits": False}),
                          ("port_trade", {}),
                          ("no_such_screen", {})):
        decision = select_rule(screen, rules, facts)
        assert (decision.macro is None) != (decision.stop_reason is None), (
            f"exactly one of macro/stop_reason must be set, got {decision}"
        )


# ── Accept 2 — drafts are inert ─────────────────────────────────────────────


def test_unapproved_rule_is_absent_and_cannot_win_by_priority():
    draft = _rule("draft", do="draft_macro", priority=99, approved=False)
    live = _rule("live", do="live_macro", priority=1, approved=True)
    decision = select_rule("port_trade", [draft, live], {})
    assert decision.macro == "live_macro", "the draft outranked the approved rule"
    assert decision.rule_id == "live"


def test_a_draft_cannot_stop_either():
    """A draft that could halt the app would still be firing.

    Canon puts drafts outside the set the collect step draws from, so they have
    no standing to produce ANY outcome -- not a macro, and not a STOP. Testing
    only "a draft cannot fire" would miss a filter placed after guard
    evaluation, which is the natural way to write it wrong.
    """
    draft_that_would_stop = _rule("draft", approved=False, guards=[_stop_guard()])
    live = _rule("live", do="live_macro", priority=1)
    decision = select_rule("port_trade", [draft_that_would_stop, live], {"credits": False})
    assert decision.macro == "live_macro"
    assert decision.stop_reason is None


def test_control_the_same_draft_fires_once_approved():
    """Non-vacuity for the two tests above.

    If the draft failed to fire for some unrelated reason -- a screen_match typo
    in the fixture, say -- both tests would pass while proving nothing about
    approval. Flipping the one field must change the outcome.
    """
    draft = _rule("draft", do="draft_macro", priority=99, approved=False)
    live = _rule("live", do="live_macro", priority=1)
    assert select_rule("port_trade", [draft, live], {}).macro == "live_macro"
    approved = Rule(**{**draft.__dict__, "approved": True})
    assert select_rule("port_trade", [approved, live], {}).macro == "draft_macro"


# ── Accept 3 — unknown facts fail closed ────────────────────────────────────


@pytest.mark.parametrize("facts", [{}, {"credits": None}, {"credits": UNKNOWN}])
def test_missing_unknown_or_null_fact_cannot_produce_a_selection(facts):
    rule = _rule(guards=[Guard(fact="credits", op="ge", value=100)])
    assert select_rule("port_trade", [rule], facts).macro is None


def test_an_unknown_fact_is_never_coerced_to_zero():
    """`credits >= 0` is the shape that catches a missing-to-zero coercion.

    A guard whose threshold is 0 passes for ANY real balance, so if the engine
    ever substituted 0 for a missing fact this rule would fire -- and it would
    look completely reasonable in a log.
    """
    rule = _rule(guards=[Guard(fact="credits", op="ge", value=0)])
    assert select_rule("port_trade", [rule], {}).macro is None
    # control: the identical rule fires the moment the fact is actually present
    assert select_rule("port_trade", [rule], {"credits": 0}).macro == "macro_a"


def test_an_unknown_fact_is_never_coerced_to_false():
    rule = _rule(guards=[Guard(fact="stale", op="is_false")])
    assert select_rule("port_trade", [rule], {}).macro is None
    assert select_rule("port_trade", [rule], {"stale": False}).macro == "macro_a"


def test_unknown_on_a_stop_posture_guard_emits_that_guards_stop():
    """Ratified 2026-07-29: fail closed toward the halt, not toward ineligible.

    A silent ineligible would let a DIFFERENT rule fire on a screen where a
    safety guard could not be evaluated at all.
    """
    stopper = _rule("stopper", guards=[_stop_guard(fact="credits", reason="credits_unknown")])
    other = _rule("other", do="other_macro", priority=1)
    decision = select_rule("port_trade", [stopper, other], {})
    assert decision.macro is None
    assert decision.stop_reason.startswith("credits_unknown")
    assert decision.rule_id == "stopper"


def test_bool_is_not_a_number_for_ordered_comparisons():
    """`True < 5` is legal Python and silently reads True as 1."""
    rule = _rule(guards=[Guard(fact="fighters", op="lt", value=5)])
    assert select_rule("port_trade", [rule], {"fighters": True}).macro is None
    assert select_rule("port_trade", [rule], {"fighters": 1}).macro == "macro_a"


def test_is_true_is_identity_not_truthiness():
    rule = _rule(guards=[Guard(fact="armed", op="is_true")])
    for truthy_but_not_true in (1, "yes", [0]):
        assert select_rule("port_trade", [rule], {"armed": truthy_but_not_true}).macro is None
    assert select_rule("port_trade", [rule], {"armed": True}).macro == "macro_a"


def test_an_undecidable_comparison_fails_rather_than_raises():
    rule = _rule(guards=[Guard(fact="credits", op="gt", value=10)])
    assert select_rule("port_trade", [rule], {"credits": "lots"}).macro is None


# ── Accept 4 — a STOP guard returns its typed reason ────────────────────────


def test_stop_guard_returns_its_typed_reason_and_no_macro():
    rule = _rule(guards=[_stop_guard(fact="credits", reason="credits_stale")])
    decision = select_rule("port_trade", [rule], {"credits": True})
    assert decision.macro is None
    assert decision.stop_reason.startswith("credits_stale")


def test_stop_outranks_a_fireable_survivor_at_any_priority():
    """Priority chooses among rules that MAY fire; a refusal is not competing."""
    stopper = _rule("stopper", priority=1, guards=[_stop_guard()])
    fireable = _rule("fireable", do="fireable_macro", priority=99)
    for order in itertools.permutations([stopper, fireable]):
        decision = select_rule("port_trade", list(order), {"credits": True})
        assert decision.macro is None, "a fireable high-priority rule beat a STOP"
        assert decision.rule_id == "stopper"


def test_stop_dominates_within_a_single_rule_too():
    rule = _rule(guards=[
        Guard(fact="cargo", op="ge", value=1),          # ineligible-posture, fails
        _stop_guard(fact="credits", reason="credits_stale"),
    ])
    decision = select_rule("port_trade", [rule], {"cargo": 0, "credits": True})
    assert decision.stop_reason.startswith("credits_stale"), (
        "an ineligible failure masked the STOP in the same rule"
    )


# ── Accept 5 — no match is a typed STOP, never a fallback ───────────────────


def test_no_matching_approved_rule_returns_a_typed_no_match_stop():
    rule = _rule(screen="port_trade")
    decision = select_rule("main_command", [rule], {})
    assert decision.macro is None
    assert decision.stop_reason.startswith(STOP_NO_CANDIDATES)


def test_all_candidates_ineligible_is_also_a_typed_stop_not_a_fallback():
    rule = _rule(guards=[Guard(fact="credits", op="ge", value=100)])
    decision = select_rule("port_trade", [rule], {"credits": 5})
    assert decision.macro is None, "an ineligible rule was fired as a fallback"
    assert decision.stop_reason.startswith(STOP_NO_CANDIDATES)


def test_an_empty_rule_set_stops_rather_than_raising():
    decision = select_rule("port_trade", [], {})
    assert decision.stop_reason.startswith(STOP_NO_CANDIDATES)


# ── Accept 6 — permutation invariance ───────────────────────────────────────


def test_selection_is_invariant_under_input_permutation():
    rules = [
        _rule("a", do="macro_a", priority=5),
        _rule("b", do="macro_b", priority=9),
        _rule("c", do="macro_c", priority=7),
        _rule("draft", do="macro_d", priority=99, approved=False),
    ]
    outcomes = {
        (select_rule("port_trade", list(order), {}).macro,
         select_rule("port_trade", list(order), {}).rule_id)
        for order in itertools.permutations(rules)
    }
    assert outcomes == {("macro_b", "b")}, f"input order changed the winner: {outcomes}"


def test_the_reported_stop_is_invariant_under_permutation():
    """Determinism must cover which STOP is reported, not just that one is."""
    rules = [
        _rule("low", priority=1, guards=[_stop_guard(fact="f1", reason="credits_stale")]),
        _rule("high", priority=9, guards=[_stop_guard(fact="f2", reason="fighters_stale")]),
    ]
    reasons = {
        select_rule("port_trade", list(order), {"f1": True, "f2": True}).stop_reason
        for order in itertools.permutations(rules)
    }
    assert len(reasons) == 1, f"the reported STOP depended on input order: {reasons}"
    assert reasons.pop().startswith("fighters_stale")


def test_equal_priority_eligible_rules_return_a_typed_ambiguity_stop():
    tie_a = _rule("a", do="macro_a", priority=7)
    tie_b = _rule("b", do="macro_b", priority=7)
    for order in itertools.permutations([tie_a, tie_b]):
        decision = select_rule("port_trade", list(order), {})
        assert decision.macro is None, "a tie silently picked a winner"
        assert decision.stop_reason.startswith(STOP_AMBIGUOUS)


def test_equal_priority_on_different_screens_is_not_ambiguous():
    """The reason ambiguity is resolved at selection time, not at parse time.

    Two rules may share a priority forever as long as they never compete on the
    same screen; rejecting that document would refuse a perfectly legal rule set.
    """
    a = _rule("a", screen="port_trade", do="macro_a", priority=7)
    b = _rule("b", screen="main_command", do="macro_b", priority=7)
    assert select_rule("port_trade", [a, b], {}).macro == "macro_a"
    assert select_rule("main_command", [a, b], {}).macro == "macro_b"


def test_a_tie_that_is_broken_by_an_ineligible_guard_is_not_ambiguous():
    """Only rules that could actually fire compete for the tie."""
    winner = _rule("a", do="macro_a", priority=7)
    blocked = _rule("b", do="macro_b", priority=7,
                    guards=[Guard(fact="credits", op="ge", value=100)])
    decision = select_rule("port_trade", [winner, blocked], {"credits": 5})
    assert decision.macro == "macro_a"


# ── Accept 7 — strict round-trip ────────────────────────────────────────────


def _full_document():
    return [
        {
            "rule_id": "haggle",
            "screen_match": "port_trade",
            "do": "auto_haggle",
            "priority": 10,
            "scope": "repeating",
            "approved": True,
            "guards": [
                {"fact": "credits", "op": "ge", "value": 100, "posture": "ineligible"},
                {"fact": "fresh_render", "op": "is_true", "posture": "stop",
                 "stop_reason": "confirm_failed"},
            ],
        },
        {
            "rule_id": "toll",
            "screen_match": "fighter_toll",
            "do": "safe_retreat",
            "priority": 20,
            "scope": "one-shot",
            "approved": False,
            "guards": [],
        },
    ]


def test_parse_serialize_parse_preserves_the_complete_document():
    once = document_from_dicts(_full_document())
    twice = document_from_dicts(document_to_dicts(once))
    assert once == twice
    # and the serialized form itself is stable, so nothing is lost on the way out
    assert document_to_dicts(once) == document_to_dicts(twice)


def test_every_declared_field_survives_the_round_trip():
    """Field-by-field, so a dropped field cannot hide behind a dataclass compare."""
    rules = document_from_dicts(_full_document())
    out = document_to_dicts(rules)
    assert out[0]["scope"] == "repeating"
    assert out[1]["scope"] == "one-shot"
    assert out[0]["approved"] is True and out[1]["approved"] is False
    assert out[0]["priority"] == 10 and out[1]["priority"] == 20
    assert out[0]["guards"][0]["value"] == 100
    assert out[0]["guards"][1]["stop_reason"] == "confirm_failed"
    assert out[0]["guards"][1]["posture"] == "stop"


def test_an_unknown_field_is_rejected_rather_than_dropped():
    """This rejection is WHY the round-trip is lossless.

    A parser that ignored unknown keys would round-trip "successfully" while
    silently discarding them -- the failure this Accept clause exists to prevent.
    """
    doc = _full_document()
    doc[0]["retry_count"] = 3
    with pytest.raises(RuleDocumentError, match="unknown field"):
        document_from_dicts(doc)


def test_a_guard_with_an_unknown_field_is_rejected_too():
    doc = _full_document()
    doc[0]["guards"][0]["tolerance"] = 5
    with pytest.raises(RuleDocumentError, match="unknown field"):
        document_from_dicts(doc)


@pytest.mark.parametrize("field", ["rule_id", "screen_match", "do", "priority"])
def test_a_missing_required_field_is_rejected(field):
    doc = _full_document()
    del doc[0][field]
    with pytest.raises(RuleDocumentError, match="missing required"):
        document_from_dicts(doc)


def test_approved_must_be_a_real_bool():
    """A truthy string is exactly how a draft goes live by accident."""
    doc = _full_document()
    doc[1]["approved"] = "false"
    with pytest.raises(RuleDocumentError, match="approved"):
        document_from_dicts(doc)


def test_priority_must_be_an_int_and_a_bool_is_not_one():
    doc = _full_document()
    doc[0]["priority"] = True
    with pytest.raises(RuleDocumentError, match="priority"):
        document_from_dicts(doc)


def test_a_stop_guard_without_a_reason_is_rejected():
    """A STOP with no typed reason would be a free-text halt."""
    doc = _full_document()
    del doc[0]["guards"][1]["stop_reason"]
    with pytest.raises(RuleDocumentError):
        document_from_dicts(doc)


def test_a_reason_on_an_ineligible_guard_is_rejected():
    """It would never be emitted; accepting it invites the author to rely on it."""
    doc = _full_document()
    doc[0]["guards"][0]["stop_reason"] = "credits_stale"
    with pytest.raises(RuleDocumentError, match="stop_reason"):
        document_from_dicts(doc)


def test_duplicate_rule_ids_are_rejected():
    doc = _full_document()
    doc[1]["rule_id"] = doc[0]["rule_id"]
    with pytest.raises(RuleDocumentError, match="duplicate"):
        document_from_dicts(doc)


@pytest.mark.parametrize("bad", ["sometimes", "", None, 7])
def test_an_unknown_scope_is_rejected(bad):
    doc = _full_document()
    doc[0]["scope"] = bad
    with pytest.raises(RuleDocumentError, match="scope"):
        document_from_dicts(doc)


def test_an_operator_outside_the_typed_set_is_rejected():
    with pytest.raises(RuleDocumentError, match="op"):
        rule_from_dict({"rule_id": "r", "screen_match": "s", "do": "m", "priority": 1,
                        "guards": [{"fact": "f", "op": "matches_regex", "value": ".*"}]})


def test_operator_arity_is_enforced_in_both_directions():
    base = {"rule_id": "r", "screen_match": "s", "do": "m", "priority": 1}
    with pytest.raises(RuleDocumentError, match="requires a 'value'"):
        rule_from_dict({**base, "guards": [{"fact": "f", "op": "ge"}]})
    with pytest.raises(RuleDocumentError, match="takes no 'value'"):
        rule_from_dict({**base, "guards": [{"fact": "f", "op": "is_true", "value": 1}]})


# ── the codes stay pinned to the real catalog ───────────────────────────────


def test_every_stop_code_this_kernel_emits_is_a_real_catalog_code():
    """The kernel may not import the catalog; this test may, and does.

    `cockpit.stopbanner` reaches `session.control_lock`, and a control-lock edge
    is forbidden to the kernel by the WO's Constraints -- so the codes live there
    as literals. That is only safe if something checks them against the real map,
    which is this. Without it, a typo'd code would render as raw text in the STOP
    banner and nothing would ever say so.
    """
    from tw2002_aiclient.cockpit.stopbanner import INTERVENTION_REASON_LABELS

    assert STOP_NO_CANDIDATES in INTERVENTION_REASON_LABELS


def test_the_ambiguity_code_is_a_disclosed_gap_not_a_typo():
    """`autopilot_ambiguous_rules` is deliberately NOT in the catalog yet.

    Canon has no equal-priority code, and the catalog is open by construction, so
    a new cause may ship its code before a label row exists (Max ruling 1A). This
    test states that on purpose: if someone later adds the label, this goes red
    and the DOC-GAP gets closed knowingly rather than drifting.
    """
    from tw2002_aiclient.cockpit.stopbanner import INTERVENTION_REASON_LABELS

    assert STOP_AMBIGUOUS not in INTERVENTION_REASON_LABELS, (
        "the ambiguity label row landed -- close the banked DOC-GAP and drop this test"
    )


def test_the_qualified_stop_shape_resolves_through_the_banner():
    """The reasons this kernel emits must survive the surface that renders them."""
    from tw2002_aiclient.cockpit.stopbanner import intervention_reason_label

    rule = _rule(guards=[_stop_guard(fact="credits", reason="credits_stale")])
    reason = select_rule("port_trade", [rule], {"credits": True}).stop_reason
    label = intervention_reason_label(reason)
    assert "credits stale" in label, f"the banner could not resolve {reason!r} -> {label!r}"


# ── the kernel stays dependency-neutral ─────────────────────────────────────


def test_the_kernel_imports_nothing_it_was_forbidden_to_import():
    """Structural, in a FRESH interpreter -- an already-loaded sibling would hide it.

    Checking `sys.modules` inside the running pytest process proves nothing: the
    suite has already imported curses, the session package and the cockpit by the
    time this runs. Only a subprocess that imports the kernel FIRST can see what
    the kernel itself drags in.
    """
    import subprocess
    import sys

    probe = (
        "import sys;"
        "import tw2002_aiclient.rule_engine;"
        "forbidden=[m for m in sys.modules if m.startswith(("
        "'curses','socket','tw2002_aiclient.session','tw2002_aiclient.cockpit',"
        "'tw2002_aiclient.loops','tw2002_aiclient.adapters'))];"
        "print(','.join(sorted(forbidden)))"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                         text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    leaked = [m for m in out.stdout.strip().split(",") if m]
    assert not leaked, f"the kernel dragged in forbidden modules: {leaked}"


def test_the_neutrality_probe_can_actually_detect_a_violation():
    """Control for the test above.

    A probe that reports "clean" because its own detection is broken is worse
    than no probe. Importing a module that DOES reach the session package must
    make the same check fire.
    """
    import subprocess
    import sys

    probe = (
        "import sys;"
        "import tw2002_aiclient.cockpit.stopbanner;"
        "forbidden=[m for m in sys.modules if m.startswith(("
        "'curses','socket','tw2002_aiclient.session','tw2002_aiclient.cockpit',"
        "'tw2002_aiclient.loops','tw2002_aiclient.adapters'))];"
        "print(','.join(sorted(forbidden)))"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                         text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip(), "the neutrality probe cannot detect anything"


def test_the_operator_table_is_the_size_this_suite_was_written_for():
    """Non-vacuity: a truncated operator table would silently narrow coverage."""
    assert set(GUARD_OPERATORS) == {
        "eq", "ne", "lt", "le", "gt", "ge", "is_true", "is_false"
    }
