"""WO-PLAY-RULES-LIBRARY — Play U)rules peeks the blessed rule store.

Read-only. Branch on ``status`` before claiming a count: absent ≠ empty ≠
blind. Drafts never appear. Product path calls ``read_rule_store``.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import rules_library
from tw2002_aiclient.rules.store import read_rule_store
from tw2002_aiclient.rules.writer import promote_draft, write_draft


def _bless(tmp_path, *, rule_id="dock-when-idle", do="dock", screen="main_command", priority=10):
    write_draft(
        {
            "rule_id": rule_id,
            "screen_match": screen,
            "do": do,
            "priority": priority,
            "approved": False,
        },
        state_dir=tmp_path,
    )
    return promote_draft(rule_id, state_dir=tmp_path)


def test_absent_store_is_not_empty_ok(tmp_path):
    report = read_rule_store(state_dir=tmp_path)
    assert rules_library.store_status(report) == "absent"
    assert rules_library.blessed_rows(report) == []
    session = rules_library.RulesLibrarySession()
    session.open([], "absent")
    lines = rules_library.compose_rule_lines(session, unicode_ok=False)
    assert any(rules_library.ABSENT_TEXT in line for line in lines)
    assert rules_library.EMPTY_TEXT not in "\n".join(lines)


def test_empty_ok_store_says_none_yet(tmp_path):
    (tmp_path / "rules").mkdir(parents=True)
    report = read_rule_store(state_dir=tmp_path)
    assert rules_library.store_status(report) == "ok"
    session = rules_library.RulesLibrarySession()
    session.open(rules_library.blessed_rows(report), "ok")
    text = "\n".join(rules_library.compose_rule_lines(session, unicode_ok=False))
    assert rules_library.EMPTY_TEXT in text
    assert rules_library.ABSENT_TEXT not in text
    assert rules_library.UNREADABLE_TEXT not in text


def test_ok_store_lists_blessed_fields(tmp_path):
    _bless(tmp_path)
    report = read_rule_store(state_dir=tmp_path)
    rows = rules_library.blessed_rows(report)
    assert rows == [
        {
            "rule_id": "dock-when-idle",
            "do": "dock",
            "screen_match": "main_command",
            "priority": 10,
        }
    ]
    session = rules_library.RulesLibrarySession()
    session.open(rows, "ok")
    text = "\n".join(
        rules_library.compose_rule_lines(session, unicode_ok=False, width=80)
    )
    assert "dock-when-idle" in text
    assert "do=dock" in text
    assert "screen=main_command" in text
    assert "prio=10" in text


def test_partial_store_banner(tmp_path):
    rules = tmp_path / "rules"
    rules.mkdir(parents=True)
    (rules / "bad.json").write_text("{not json", encoding="utf-8")
    _bless(tmp_path, rule_id="ok-rule", do="land", screen="port_menu", priority=3)
    report = read_rule_store(state_dir=tmp_path)
    assert rules_library.store_status(report) == "partial"
    session = rules_library.RulesLibrarySession()
    session.open(rules_library.blessed_rows(report), "partial")
    lines = rules_library.compose_rule_lines(session, unicode_ok=False)
    assert rules_library.PARTIAL_BANNER in lines
    assert any("ok-rule" in line for line in lines)


def test_unreadable_is_not_zero_rules(tmp_path):
    # A file where a directory should be — store reports unreadable.
    bogus = tmp_path / "rules"
    bogus.write_text("not a dir", encoding="utf-8")
    report = read_rule_store(state_dir=tmp_path)
    assert rules_library.store_status(report) == "unreadable"
    session = rules_library.RulesLibrarySession()
    session.open([], "unreadable")
    text = "\n".join(rules_library.compose_rule_lines(session, unicode_ok=False))
    assert rules_library.UNREADABLE_TEXT in text
    assert rules_library.EMPTY_TEXT not in text


def test_drafts_never_appear(tmp_path):
    write_draft(
        {
            "rule_id": "still-draft",
            "screen_match": "main_command",
            "do": "dock",
            "priority": 1,
            "approved": False,
        },
        state_dir=tmp_path,
    )
    report = read_rule_store(state_dir=tmp_path)  # include_drafts=False
    assert rules_library.blessed_rows(report) == []


def test_play_u_intent_is_pure_and_no_send():
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    assert play.handle_key(ord("u")) == "rules_library_open"
    play.rules_library_session.open([], "absent")
    assert play.handle_key(ord("u")) == "rules_library_close"
    src = inspect.getsource(rules_library)
    assert "send_key" not in src
    assert "session.send" not in src
    assert "send_request" not in src


def test_play_enter_does_not_arm_while_peek_open():
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    play.rules_library_session.open(
        [{"rule_id": "r", "do": "d", "screen_match": "s", "priority": 1}],
        "ok",
    )
    assert play.handle_key(10) is None
    assert play.handle_key(13) is None


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


def test_run_play_calls_read_rule_store():
    called = _run_play_calls()
    assert "read_rule_store" in called
    assert "blessed_rows" in called
    assert "store_status" in called
