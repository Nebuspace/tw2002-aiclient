"""WO-WIRE-COVERAGE-LEDGER-COUNTS — live_actor_counts for the coverage meter."""

from __future__ import annotations

import json
from pathlib import Path

from tw2002_aiclient.ledger import live_actor_counts
from tw2002_aiclient.cockpit.covermeter import compose_coverage_meter


def _row(actor: str) -> dict:
    return {
        "actor": actor,
        "input": "x",
        "settled_class": "main_command",
        "reward": {},
    }


def test_absent_ledger_is_unavailable(tmp_path: Path) -> None:
    missing = tmp_path / "nope.jsonl"
    assert live_actor_counts(missing) == (None, None)
    assert compose_coverage_meter(app=None, human=None) == "COV ?"


def test_empty_ledger_is_known_zero(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text("", encoding="utf-8")
    assert live_actor_counts(path) == (0, 0)
    assert compose_coverage_meter(app=0, human=0) == "COV ? · App 0 · Hum 0"


def test_counts_app_and_human_only(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    rows = [_row("app"), _row("app"), _row("human"), _row("app"), {"input": "z"}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert live_actor_counts(path) == (3, 1)
    assert compose_coverage_meter(app=3, human=1) == "COV 75% · App 3 · Hum 1"


def test_screens_draw_path_reads_ledger_counts() -> None:
    """Mutation pin: product draw must call live_actor_counts (not hardcode None)."""
    src = Path(__file__).resolve().parents[1] / "tw2002_aiclient" / "screens.py"
    text = src.read_text(encoding="utf-8")
    assert "from tw2002_aiclient.ledger import live_actor_counts" in text
    assert "live_actor_counts(" in text
    assert "getattr(self, \"ledger_path\", None)" in text
    # Stale always-None wire must not return
    assert "compose_coverage_meter(\n                        app=None, human=None" not in text
