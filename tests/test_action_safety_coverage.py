"""PWO-112 — action-safety coverage map pins (unit per guard class)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import action_safety
from tw2002_aiclient.action_safety import GuardCoverage, assert_coverage_map_intact


def test_coverage_map_intact() -> None:
    """Every canon guard class still has source marker + proof file."""
    assert_coverage_map_intact()


def test_coverage_ids_unique_and_nonempty() -> None:
    ids = [g.guard_id for g in action_safety.all_coverage()]
    assert ids
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("entry", action_safety.all_coverage(), ids=lambda g: g.guard_id)
def test_unit_per_guard_class_source_and_proof(entry: GuardCoverage) -> None:
    """Unit-per-class: each inventory row's pins resolve on tip."""
    src = action_safety.source_path(entry)
    proof = action_safety.proof_path(entry)
    assert src.is_file(), entry.guard_id
    assert proof.is_file(), entry.guard_id
    assert entry.source_marker in src.read_text(encoding="utf-8")
    assert entry.proof_marker in proof.read_text(encoding="utf-8")
    assert entry.canon_layer.strip()
    assert entry.notes.strip()


def test_map_covers_canon_schema_core_layers() -> None:
    """Schema ladder layers from action-safety-guards.md must appear."""
    layers = {g.canon_layer for g in action_safety.all_coverage()}
    for required in ("Per-send", "Per-cycle", "Resolver", "Run", "Crawl", "Always"):
        assert required in layers, required


def test_never_auto_inventory_is_referenced_not_replaced() -> None:
    """NEVER_AUTO consumer audit remains the money_prompt depth proof."""
    entry = next(g for g in action_safety.all_coverage() if g.guard_id == "never_auto_money_prompt")
    assert entry.proof_test_relpath == "tests/test_never_auto_action.py"
    audit = Path(__file__).resolve().parents[1] / "audit" / "never-auto-action-consumer-audit-20260726.md"
    assert audit.is_file()
