"""``tw mine`` / ``tw patterns`` CLI wiring (WO-BUILD-WIRE-TW-MINE-CLI-VERB)."""

from __future__ import annotations

import json

from tw2002_aiclient import mine_cli
from tw2002_aiclient.session import cli


def test_mine_no_propose_on_empty_ledger(tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("", encoding="utf-8")
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    rc = mine_cli.cmd_mine(
        cli.build_parser().parse_args(
            [
                "mine",
                "--ledger",
                str(ledger),
                "--drafts",
                str(drafts),
                "--no-propose",
            ]
        )
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "patterns=0" in out
    assert "drafts=0" in out
    assert list(drafts.iterdir()) == []


def test_mine_json_shape(tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("", encoding="utf-8")
    rc = mine_cli.cmd_mine(
        cli.build_parser().parse_args(
            ["mine", "--ledger", str(ledger), "--no-propose", "--json"]
        )
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["propose"] is False
    assert payload["patterns"] == []
    assert payload["drafts"] == []


def test_patterns_alias_shares_handler():
    parser = cli.build_parser()
    mine = parser.parse_args(["mine"])
    patterns = parser.parse_args(["patterns", "--top-k", "5"])
    assert mine.func is patterns.func is mine_cli.cmd_mine
    assert patterns.top_k == 5
