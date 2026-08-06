"""Tests for WO-BUILD-POST-SESSION-ACTION-REPORT."""

from __future__ import annotations

import json
from pathlib import Path

from tw2002_aiclient.ledger import LedgerWriter
from tw2002_aiclient.session_report import (
    build_session_report,
    format_session_report,
    write_session_report,
)


def _row(writer: LedgerWriter, **kwargs):
    defaults = dict(
        pre_text="Command [TL=1000]:\n",
        input_text="1",
        secret=False,
        post_text="Command [TL=999]:\n",
        settled_class="command",
        actor="app",
        session_id="s-test",
    )
    defaults.update(kwargs)
    return writer.record_do(**defaults)


def test_report_lists_app_actions_with_rule_and_screen(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter(ledger)
    _row(w, rule_id="rule-trade-1", settled_class="port_trade", input_text="158")
    _row(w, actor="human", settled_class="command", input_text="M1")
    _row(
        w,
        rule_id="rule-pvp",
        settled_class="fighter_toll",
        target_player="EnemyTrader",
        input_text="A",
    )

    report = build_session_report(path=ledger, session_id="s-test")
    assert report.human_count == 1
    assert len(report.app_actions) == 2
    assert report.app_actions[0].rule_id == "rule-trade-1"
    assert report.app_actions[0].screen == "port_trade"
    assert report.app_actions[0].ts
    assert report.app_actions[1].target_player == "EnemyTrader"

    text = format_session_report(report)
    assert "rule=rule-trade-1" in text
    assert "screen=port_trade" in text
    assert "target=EnemyTrader" in text


def test_report_skips_interrupted_by_default(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter(ledger)
    _row(w, rule_id="ok", interrupted_by_human=False)
    _row(w, rule_id="bad", interrupted_by_human=True)
    report = build_session_report(path=ledger)
    assert len(report.app_actions) == 1
    assert report.skipped_interrupted == 1
    assert report.app_actions[0].rule_id == "ok"


def test_report_write_file_artifact(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter(ledger)
    _row(w, rule_id="r1")
    report = build_session_report(path=ledger)
    out = tmp_path / "report.txt"
    write_session_report(report, out)
    body = out.read_text(encoding="utf-8")
    assert "Post-session action report" in body
    assert "rule=r1" in body


def test_report_cli_json(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace

    from tw2002_aiclient.session import cli

    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter(ledger)
    _row(w, rule_id="cli-rule", settled_class="computer")

    args = SimpleNamespace(
        ledger=str(ledger),
        session_id="s-test",
        world_id=None,
        out=None,
        include_interrupted=False,
        json=True,
    )

    import io
    import sys

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    assert cli.cmd_report(args) == 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True
    assert payload["app_actions"][0]["rule_id"] == "cli-rule"
    assert payload["app_actions"][0]["screen"] == "computer"
