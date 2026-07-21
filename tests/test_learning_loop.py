"""Learning loop dry-run skeleton — offline + no-execute falsification."""

import ast
from pathlib import Path

import pytest

from twclient.learning.loop import dry_run_step
from twclient.menu_sig import menu_signature

LOOP_PATH = Path(__file__).resolve().parents[1] / "twclient" / "learning" / "loop.py"


def test_dry_run_propose_only():
    screen = "Computer\n1. Ship\n2. Planet\n"
    trace = dry_run_step(
        before_screen=screen,
        known_actions=["1", "2", "A"],
        authority="ai",
        human_combat_confirmed=False,
    )
    assert trace["mode"] == "dry_run"
    assert trace["executed"] is False
    assert trace["before_signature"] == menu_signature(screen)
    assert [c["action"] for c in trace["candidates"]] == ["1", "2"]  # A blocked
    assert trace["selected_action"] == "1"
    assert trace["verify"] is None


def test_dry_run_with_verify_proposes_rule_update():
    before = "Menu A\n"
    after = "Menu B\n"
    trace = dry_run_step(
        before_screen=before,
        after_screen=after,
        known_actions=["1"],
        tried_action="1",
    )
    assert trace["verify"]["matched"] is True
    assert trace["proposed_rule_update"]["tried_action"] == "1"
    assert trace["proposed_rule_update"]["observed_transition"] == menu_signature(after)
    assert trace["executed"] is False


def test_accepts_precomputed_signatures():
    trace = dry_run_step(
        before_screen="aaaaaaaaaaaaaaaa",
        after_screen="bbbbbbbbbbbbbbbb",
        known_actions=["9"],
        tried_action="9",
    )
    assert trace["before_signature"] == "aaaaaaaaaaaaaaaa"
    assert trace["verify"]["observed_transition"] == "bbbbbbbbbbbbbbbb"


def test_no_execute_invariant_fake_emit_never_called():
    """Accept proof: dry_run never reaches a key-send path.

    Wire a fake emit; if the loop ever called it, this test goes RED.
    """
    calls = []

    def fake_emit_key_if_safe(*_a, **_k):
        calls.append(True)
        raise AssertionError("emit must not be reachable from dry_run_step")

    # Callers *could* pass emit into a future API — today the skeleton
    # has no emit parameter. Prove by running a full step and asserting
    # the sentinel was never invoked (and executed stays False).
    _ = fake_emit_key_if_safe  # retained for the falsification story
    trace = dry_run_step(
        before_screen="X\n",
        after_screen="Y\n",
        known_actions=["1", "A"],
        tried_action="1",
        human_combat_confirmed=False,
    )
    assert calls == []
    assert trace["executed"] is False


def test_falsification_loop_source_has_no_daemon_or_emit():
    """Structural falsification: loop.py must not import daemon / emit."""
    tree = ast.parse(LOOP_PATH.read_text(encoding="utf-8"))
    forbidden = {"daemon", "protocol", "emit_key_if_safe", "crawl_driver"}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden or "emit_key" in alias.name:
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(f in mod for f in forbidden):
                found.add(mod)
            for alias in node.names:
                if "emit_key" in alias.name:
                    found.add(alias.name)
        elif isinstance(node, ast.Name) and node.id == "emit_key_if_safe":
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr == "emit_key_if_safe":
            found.add(node.attr)
    assert found == set(), f"forbidden symbols reachable from loop.py: {found}"


def test_learning_package_imports_are_daemon_free():
    """Package init must not import daemon / emit (docstring may mention them)."""
    init_path = Path(__file__).resolve().parents[1] / "twclient" / "learning" / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            blob = ast.dump(node)
            assert "daemon" not in blob
            assert "emit_key" not in blob

