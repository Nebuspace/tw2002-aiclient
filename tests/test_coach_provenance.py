"""WO-BUILD-COVERAGE-METRICS-TEACHING-PROVENANCE-WIRE — product callers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tw2002_aiclient.coverage_metrics import (
    ORIGIN_BUCKET_UNKNOWN,
    format_teaching_provenance_line,
    teaching_provenance_counts,
)
from tw2002_aiclient.ledger import LedgerWriter
from tw2002_aiclient.rule_engine import ORIGIN_AI_APPROVED, ORIGIN_HUMAN
from tw2002_aiclient.rules.writer import promote_draft, write_draft
from tw2002_aiclient.session_report import build_session_report, format_session_report


def _base(**extra):
    doc = {
        "rule_id": "dock-when-idle",
        "screen_match": "main_command",
        "do": "dock",
        "priority": 10,
        "approved": False,
    }
    doc.update(extra)
    return doc


def _seed_rules(tmp_path: Path) -> None:
    write_draft(
        {**_base(rule_id="human-rule", origin=ORIGIN_HUMAN), "approved": False},
        state_dir=tmp_path,
    )
    promote_draft("human-rule", state_dir=tmp_path)
    write_draft(
        {
            **_base(rule_id="ai-rule", origin=ORIGIN_AI_APPROVED),
            "approved": False,
        },
        state_dir=tmp_path,
    )
    promote_draft("ai-rule", state_dir=tmp_path)


def test_format_teaching_provenance_line_empty_share_is_question() -> None:
    counts = {
        ORIGIN_HUMAN: 0,
        ORIGIN_AI_APPROVED: 0,
        ORIGIN_BUCKET_UNKNOWN: 0,
        "total": 0,
    }
    line = format_teaching_provenance_line(counts)
    assert "ai-share=?" in line
    assert "total=0" in line


def test_session_report_includes_teaching_provenance(tmp_path: Path) -> None:
    _seed_rules(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter(ledger)
    w.record_do(
        pre_text="Command [TL=1000]:\n",
        input_text="1",
        secret=False,
        post_text="Command [TL=999]:\n",
        settled_class="command",
        actor="app",
        session_id="s-test",
        rule_id="human-rule",
    )
    report = build_session_report(path=ledger, state_dir=tmp_path, session_id="s-test")
    assert report.teaching_provenance is not None
    assert report.teaching_provenance["total"] == 2
    assert report.teaching_provenance[ORIGIN_HUMAN] == 1
    assert report.teaching_provenance[ORIGIN_AI_APPROVED] == 1
    text = format_session_report(report)
    assert "teaching provenance" in text
    assert "ai-approved=1" in text


def test_coach_provenance_cli_text_and_json(tmp_path: Path) -> None:
    from tw2002_aiclient.coach_cli import cmd_coach_provenance

    _seed_rules(tmp_path)
    args = SimpleNamespace(state_dir=str(tmp_path), world_id=None, json=False)
    import io
    import sys

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = cmd_coach_provenance(args)
    finally:
        sys.stdout = old
    assert rc == 0
    out = buf.getvalue()
    assert "teaching provenance" in out
    assert "human=1" in out

    args_json = SimpleNamespace(state_dir=str(tmp_path), world_id=None, json=True)
    buf2 = io.StringIO()
    sys.stdout = buf2
    try:
        rc2 = cmd_coach_provenance(args_json)
    finally:
        sys.stdout = old
    assert rc2 == 0
    payload = json.loads(buf2.getvalue())
    assert payload["ok"] is True
    assert payload["counts"]["total"] == 2
    assert payload["ai_share"] == 0.5


def test_teaching_provenance_counts_is_product_callable(tmp_path: Path) -> None:
    """Regression pin: session_report is a non-test product caller."""
    _seed_rules(tmp_path)
    from tw2002_aiclient.rules.store import read_rule_store

    rules = read_rule_store(state_dir=tmp_path)["rules"]
    counts = teaching_provenance_counts(rules)
    assert counts["total"] == 2
