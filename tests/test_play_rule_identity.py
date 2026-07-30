"""WO-PLAY-RULE-IDENTITY / WO-PLAY-RULE-SCOPE — Play typed entry for
rule_id / do / priority / scope.

After Analyze `y`, the operator types four fields on the control strip
(Enter advances; Esc cancels). Only a complete quadruple reaches
``write_draft`` → ``promote_draft``. No minted defaults — including
``scope`` (never a silent one-shot).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import draft_approve
from tw2002_aiclient.rules.reflex import propose_macro
from tw2002_aiclient.rules.store import rules_dir


def _type_field(session: dict, text: str) -> str:
    """Type *text* then Enter; return the final resolve outcome."""
    for ch in text:
        assert draft_approve.resolve_identity_key(session, ord(ch)) == draft_approve.CONTINUE
    return draft_approve.resolve_identity_key(session, 10)


def test_blank_field_refuses_and_writes_nothing(tmp_path):
    stub = draft_approve.create_analyze_draft("main_command")
    session = draft_approve.create_identity_session(stub)
    assert _type_field(session, "") == draft_approve.REFUSE
    assert "required" in (session.get("refuse_reason") or "")
    assert not (tmp_path / "rules").exists()


def test_whitespace_only_rule_id_refuses():
    session = draft_approve.create_identity_session(
        draft_approve.create_analyze_draft("main_command")
    )
    assert _type_field(session, "   ") == draft_approve.REFUSE
    assert session.get("values") == {}


def test_non_int_priority_refuses():
    session = draft_approve.create_identity_session(
        draft_approve.create_analyze_draft("main_command")
    )
    assert _type_field(session, "dock-idle") == draft_approve.CONTINUE
    assert _type_field(session, "dock") == draft_approve.CONTINUE
    assert _type_field(session, "nope") == draft_approve.REFUSE
    assert "int" in (session.get("refuse_reason") or "")
    assert "priority" not in session.get("values", {})


def test_blank_scope_refuses():
    session = draft_approve.create_identity_session(
        draft_approve.create_analyze_draft("main_command")
    )
    assert _type_field(session, "r") == draft_approve.CONTINUE
    assert _type_field(session, "d") == draft_approve.CONTINUE
    assert _type_field(session, "1") == draft_approve.CONTINUE
    assert _type_field(session, "") == draft_approve.REFUSE
    assert "scope" in (session.get("refuse_reason") or "")


def test_unknown_scope_refuses():
    session = draft_approve.create_identity_session(
        draft_approve.create_analyze_draft("main_command")
    )
    assert _type_field(session, "r") == draft_approve.CONTINUE
    assert _type_field(session, "d") == draft_approve.CONTINUE
    assert _type_field(session, "1") == draft_approve.CONTINUE
    assert _type_field(session, "always") == draft_approve.REFUSE
    assert "one-shot" in (session.get("refuse_reason") or "")
    assert "scope" not in session.get("values", {})


def test_esc_cancels_with_nothing_written(tmp_path):
    session = draft_approve.create_identity_session(
        draft_approve.create_analyze_draft("main_command")
    )
    for ch in "partial":
        draft_approve.resolve_identity_key(session, ord(ch))
    assert draft_approve.resolve_identity_key(session, 27) == draft_approve.CANCEL
    assert not (tmp_path / "rules").exists()


def test_complete_fields_bridge_write_promote_and_reflex_sees_it(tmp_path):
    stub = draft_approve.create_analyze_draft("main_command")
    session = draft_approve.create_identity_session(stub)
    assert _type_field(session, "dock-when-idle") == draft_approve.CONTINUE
    assert _type_field(session, "dock") == draft_approve.CONTINUE
    assert _type_field(session, "10") == draft_approve.CONTINUE
    assert _type_field(session, "repeating") == draft_approve.COMPLETE

    values = session["values"]
    assert values["scope"] == "repeating"
    document = draft_approve.bridge_to_kernel_document(
        stub,
        rule_id=values["rule_id"],
        do=values["do"],
        priority=values["priority"],
        scope=values["scope"],
    )
    from tw2002_aiclient.rules.writer import promote_draft, write_draft

    write_draft(document, state_dir=tmp_path)
    path = promote_draft("dock-when-idle", state_dir=tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["approved"] is True
    assert payload["scope"] == "repeating"
    assert path.parent == rules_dir(tmp_path)
    after = propose_macro("main_command", {}, state_dir=tmp_path)
    assert after.macro == "dock"
    assert after.rule_id == "dock-when-idle"


def test_play_screen_routes_y_then_typed_entry():
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    draft = draft_approve.create_analyze_draft("main_command")
    play.pending_analyze_draft = draft
    play.begin_draft_approve(draft)
    assert play.handle_key(ord("y")) == "draft_approve"
    play.begin_rule_identity(draft)
    assert play._rule_identity is not None

    for ch in "r1":
        assert play.handle_key(ord(ch)) is None
    assert play.handle_key(10) is None  # advance to do
    for ch in "m1":
        assert play.handle_key(ord(ch)) is None
    assert play.handle_key(10) is None  # advance to priority
    for ch in "3":
        assert play.handle_key(ord(ch)) is None
    assert play.handle_key(10) is None  # advance to scope
    for ch in "one-shot":
        assert play.handle_key(ord(ch)) is None
    assert play.handle_key(10) == "rule_identity"
    assert play._rule_identity["values"] == {
        "rule_id": "r1",
        "do": "m1",
        "priority": 3,
        "scope": "one-shot",
    }


def test_play_screen_esc_cancels_identity():
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    play.begin_rule_identity(draft_approve.create_analyze_draft("x"))
    assert play.handle_key(27) == "rule_identity_cancel"
    assert play._rule_identity is None


def test_blessed_status_line_names_rule_and_v():
    line = draft_approve.compose_rule_blessed_line(
        "dock-when-idle", "dock", "repeating",
    )
    assert "dock-when-idle" in line
    assert "dock" in line
    assert "repeating" in line
    assert "V can propose" in line
    assert "multi-pass" in line

    one = draft_approve.compose_rule_blessed_line(
        "dock-when-idle", "dock", "one-shot",
    )
    assert "one-pass" in one


def _run_play_calls() -> set:
    import tw2002_aiclient.app as app_mod

    tree = ast.parse(Path(app_mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_play":
            return {
                getattr(c.func, "attr", None) or getattr(c.func, "id", None)
                for c in ast.walk(node)
                if isinstance(c, ast.Call)
            }
    raise AssertionError("app._run_play not found")


def test_run_play_wires_bridge_write_and_promote():
    """Wiring pin: y→identity→bless uses the real writer, not the CLI hint."""
    called = _run_play_calls()
    assert "bridge_to_kernel_document" in called
    assert "write_draft" in called
    assert "promote_draft" in called
    assert "begin_rule_identity" in called
    assert "compose_bridge_command" not in called
    assert "compose_rule_blessed_line" in called


def test_false_cli_only_claim_is_gone():
    import tw2002_aiclient.app as app_mod

    tree = ast.parse(Path(app_mod.__file__).read_text(encoding="utf-8"))
    said = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert not [s for s in said if "not yet a rule" in s]
    assert not [s for s in said if "playback-eligible" in s]
    assert any(s == "analyze_rule_written" for s in said)
    # Success copy lives on the composer (shared with the status line).
    assert "V can propose" in draft_approve.compose_rule_blessed_line("r", "m")
