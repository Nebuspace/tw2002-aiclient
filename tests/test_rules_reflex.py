"""WO-RULE-ENGINE-WIRE, Accept 2 -- a product path reaches the kernel with a
real screen class and real facts, and gets a macro name or a typed STOP.

Also pins the thing this slice could plausibly get wrong: that making the
reflex layer *reachable* did not make it *able to act*. `rules/` holds no send
path, and the `reflex` verb takes no control lock and issues no keystroke.

**On Accepts 3 and 4** (arm false -> no send; disarm observed within one
boundary): those are pinned on `main` already, by
`tests/test_loop_player.py::test_an_abort_mid_loop_stops_within_one_send_step`
(drives `aborts=[False, True]` and asserts `sends == [("P", None)]` -- one
send, not two) and `::test_a_fence_outranks_an_abort_in_the_reported_reason`
(`sends == []`). Deliberately NOT duplicated here: a second guard over
behaviour a sibling already covers is unreachable, untested, and rots without
anyone noticing.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tw2002_aiclient.halt_reasons import halt_reason_code
from tw2002_aiclient.rule_engine import STOP_AMBIGUOUS, STOP_NO_CANDIDATES
from tw2002_aiclient.rules import reflex as reflex_mod
from tw2002_aiclient.rules.reflex import (
    STATUS_FACT_KEYS,
    STOP_RULES_UNREADABLE,
    facts_from_status,
    propose_macro,
)

APPROVED = {
    "rule_id": "dock-when-idle",
    "screen_match": "command_prompt",
    "do": "dock",
    "priority": 10,
    "approved": True,
}


def write_rules(tmp_path: Path, *documents) -> Path:
    d = tmp_path / "rules"
    d.mkdir(parents=True, exist_ok=True)
    for i, doc in enumerate(documents):
        (d / f"r{i}.json").write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
    return d


# ---------------------------------------------------------------------------
# Selection through the real store
# ---------------------------------------------------------------------------


def test_an_approved_rule_matching_the_screen_proposes_its_macro(tmp_path):
    write_rules(tmp_path, APPROVED)
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert decision.macro == "dock"
    assert decision.rule_id == "dock-when-idle"
    assert decision.stop_reason is None


def test_a_draft_rule_proposes_nothing_even_at_a_towering_priority(tmp_path):
    write_rules(tmp_path, {**APPROVED, "approved": False, "priority": 9999})
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert decision.macro is None
    assert halt_reason_code(decision.stop_reason) == STOP_NO_CANDIDATES


def test_a_guard_on_a_fact_nobody_measured_fails_closed(tmp_path):
    """The store carries the guard; the status payload has no such fact.

    The kernel resolves a missing fact to `UNKNOWN`, whose `__bool__` raises,
    so it cannot be coerced into a pass. This is the end-to-end proof that the
    property survives the wire, not just the unit test.
    """
    write_rules(
        tmp_path,
        {**APPROVED, "guards": [{"fact": "credits", "op": "gt", "value": 1000}]},
    )
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert decision.macro is None
    assert halt_reason_code(decision.stop_reason) == STOP_NO_CANDIDATES


def test_a_guard_whose_fact_is_present_and_satisfied_still_fires(tmp_path):
    """Non-vacuity control for the test above.

    Without this, a reflex layer that refused *everything* would pass the
    fails-closed test perfectly.
    """
    write_rules(
        tmp_path,
        {**APPROVED, "guards": [{"fact": "idle_ms", "op": "gt", "value": 500}]},
    )
    decision = propose_macro("command_prompt", {"idle_ms": 900}, state_dir=tmp_path)

    assert decision.macro == "dock"


def test_two_approved_rules_at_the_same_priority_return_the_ambiguity_stop(tmp_path):
    write_rules(tmp_path, APPROVED, {**APPROVED, "rule_id": "other", "do": "trade"})
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert decision.macro is None, "a tie must never be broken by filesystem order"
    assert halt_reason_code(decision.stop_reason) == STOP_AMBIGUOUS


# ---------------------------------------------------------------------------
# An unreadable library is not an empty one
# ---------------------------------------------------------------------------


def test_an_absent_library_reports_a_completed_search(tmp_path):
    """`absent` authorises the settled negative, and that is correct.

    There are no rules, so "no rule matched" is exactly true -- which is why
    `absent` is on the authorising list and `partial` is not.
    """
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)
    assert halt_reason_code(decision.stop_reason) == STOP_NO_CANDIDATES


def test_a_partly_read_library_refuses_rather_than_answering_from_what_parsed(tmp_path):
    """The safety call this module exists to make.

    Every rule that parsed is individually valid, so answering from them looks
    reasonable. But selection is a COMPARISON across the whole candidate set,
    and the file that failed to parse could hold a higher-priority rule or a
    `stop`-posture veto. Dropping it can turn a STOP into a fire and cannot do
    the reverse, so `partial` authorises nothing.
    """
    write_rules(tmp_path, APPROVED, "{not json")
    decision = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert decision.macro is None, "a partly-read library must not fire a macro"
    assert halt_reason_code(decision.stop_reason) == STOP_RULES_UNREADABLE


def test_the_partial_refusal_is_not_just_a_broken_store(tmp_path):
    """Non-vacuity control: the SAME good rule fires once the corrupt file goes.

    Without this, the test above would pass against a store that could never
    load anything at all.
    """
    write_rules(tmp_path, APPROVED)
    assert propose_macro("command_prompt", {}, state_dir=tmp_path).macro == "dock"


def test_unreadable_and_no_candidates_do_not_share_a_reason_code(tmp_path):
    """They are indistinguishable to any caller that only checks `macro is
    None`, which is precisely why the codes must differ."""
    write_rules(tmp_path, APPROVED, "{not json")
    unreadable = propose_macro("command_prompt", {}, state_dir=tmp_path)
    write_rules(tmp_path)  # a clean, empty store
    (tmp_path / "rules" / "r0.json").unlink(missing_ok=True)
    (tmp_path / "rules" / "r1.json").unlink(missing_ok=True)
    empty = propose_macro("command_prompt", {}, state_dir=tmp_path)

    assert unreadable.macro is empty.macro is None
    assert halt_reason_code(unreadable.stop_reason) != halt_reason_code(empty.stop_reason)


def test_an_unnameable_screen_matches_no_rule(tmp_path):
    write_rules(tmp_path, APPROVED)
    for klass in (None, "", 17):
        decision = propose_macro(klass, {}, state_dir=tmp_path)
        assert decision.macro is None, f"{klass!r} must not select a macro"


# ---------------------------------------------------------------------------
# Facts: absent, never defaulted
# ---------------------------------------------------------------------------


def test_a_missing_status_key_is_omitted_not_defaulted():
    facts = facts_from_status({"connected": True})
    assert facts == {"connected": True}
    for key in STATUS_FACT_KEYS:
        if key != "connected":
            assert key not in facts, f"{key} was invented from an absent value"


def test_an_explicit_none_is_dropped_because_it_is_an_absence_wearing_a_value():
    assert facts_from_status({"connected": None, "idle_ms": 40}) == {"idle_ms": 40}


def test_a_non_mapping_status_yields_no_facts_rather_than_raising():
    for payload in (None, [], "status", 3):
        assert facts_from_status(payload) == {}


def test_falsy_but_real_values_survive():
    """`0` and `False` are measurements, not absences.

    A truthiness filter here would silently drop `idle_ms: 0` -- the freshest
    possible reading -- and a guard on it would then fail closed for no
    reason.
    """
    facts = facts_from_status({"idle_ms": 0, "connected": False, "subscribers": 0})
    assert facts == {"idle_ms": 0, "connected": False, "subscribers": 0}


# ---------------------------------------------------------------------------
# The package cannot act
# ---------------------------------------------------------------------------

_SEND_NAMES = {
    "send",
    "send_raw",
    "send_and_confirm",
    "send_key",
    "send_request",
    "replay_loop",
    "autoloop_start",
    "take_human",
    "enter_auto_loop",
}


def test_the_rules_package_contains_no_send_or_arm_call():
    """Structural tripwire, WO-P4-055's precedent.

    Making the kernel reachable is the whole slice; making it *able to act*
    would be a different and un-ruled change. This is scoped to the whole
    module rather than one function, because `app.py`'s legitimate `status`
    call lives in a nested closure that a function-scoped guard would miss.
    A dynamic/non-literal call name is not exempted -- an opaque verb cannot
    be statically proven safe -- but there are none here today.
    """
    package = Path(reflex_mod.__file__).parent
    offenders = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in _SEND_NAMES:
                offenders.append(f"{path.name}:{node.lineno} calls {name}")
    assert offenders == [], (
        f"the rules package must propose, never act -- found {offenders}"
    )


def test_the_no_send_tripwire_can_detect_a_send(tmp_path):
    """Control. A scan that matched nothing would pass on a broken walk."""
    planted = tmp_path / "acts.py"
    planted.write_text("def go(session):\n    session.send_and_confirm('d', None)\n")
    tree = ast.parse(planted.read_text())
    names = [
        getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
    ]
    assert "send_and_confirm" in names
    assert _SEND_NAMES & set(names)


def test_propose_macro_touches_no_session_at_all(tmp_path):
    """It has no parameter through which a session could arrive.

    The strongest form of "it cannot send": not a guard that refuses, but a
    signature with nothing to refuse WITH. `loops/player.py` makes the same
    argument about its own `session` parameter having no default.
    """
    import inspect

    params = set(inspect.signature(propose_macro).parameters)
    assert not (params & {"session", "port", "conn", "control_lock"}), (
        f"propose_macro grew a way to reach the wire: {params}"
    )


# ---------------------------------------------------------------------------
# The product path: the `reflex` verb
# ---------------------------------------------------------------------------


class _BareServer:
    """No `control_lock`/`watch_hub` -- protocol reads both via `getattr`."""


def test_the_reflex_verb_returns_the_kernels_answer(tmp_path, monkeypatch):
    """Accept 2 end to end: a real dispatch, a real classification, a real store."""
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    write_rules(tmp_path, {**APPROVED, "screen_match": "command_prompt"})
    monkeypatch.setattr(reflex_mod, "read_rule_store", _store_from(tmp_path))

    session = Session("twgs.test.example", 23, None, str(tmp_path))
    session.conn._sock = _StubSocket()
    session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? :")

    resp = protocol.dispatch(session, "reflex", {}, _BareServer())

    assert resp["ok"] is True
    assert resp["classification"] == "main_command"
    assert set(resp["reflex"]) == {"macro", "rule_id", "stop_reason", "scope"}


def test_the_reflex_verb_sends_nothing(tmp_path, monkeypatch):
    """Proven by a socket that RAISES on write, not by inspecting a log.

    A refusal proven by reading what was logged is a refusal proven by the
    same code that would have done the sending.
    """
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    write_rules(tmp_path, APPROVED)
    monkeypatch.setattr(reflex_mod, "read_rule_store", _store_from(tmp_path))

    session = Session("twgs.test.example", 23, None, str(tmp_path))
    session.conn._sock = _ExplodingSocket()
    session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? :")

    resp = protocol.dispatch(session, "reflex", {}, _BareServer())
    assert resp["ok"] is True


def test_an_unknown_verb_is_still_refused():
    """Control for the dispatch tests: proves `dispatch` can say no, so a
    passing `reflex` call is a real branch and not a permissive default."""
    from tw2002_aiclient.session import protocol

    resp = protocol.dispatch(None, "reflexx", {}, _BareServer())
    assert resp["ok"] is False
    assert resp["error"] == "unknown_verb:reflexx"


def _store_from(tmp_path):
    from tw2002_aiclient.rules.store import read_rule_store as real

    def loader(*, state_dir=None, rules_path=None):
        return real(state_dir=tmp_path)

    return loader


class _StubSocket:
    def sendall(self, _data):
        return None

    def close(self):
        return None


class _ExplodingSocket:
    def sendall(self, _data):  # pragma: no cover - firing IS the failure
        raise AssertionError("the reflex verb wrote to the wire")

    def close(self):
        return None
