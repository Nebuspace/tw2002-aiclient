"""`tw log`/`tw trail` CLI verb tests -- no daemon involved, reads
state/ledger.jsonl directly (DESIGN-v2.md §10)."""

import json
from argparse import Namespace

from twclient import cli, ledger


def _write_entry(path, **overrides):
    entry = {
        "ts": "2026-07-19T07:08:45Z",
        "capture": None,
        "prompt": "your offer [158]?",
        "pre_state": {"credits": 96553},
        "input": "158",
        "post_state": {"credits": 96783},
        "settled_class": "port_trade",
        "screen_delta_summary": "+1/-1/~0 lines",
        "reward": {"d_credits": 230},
    }
    entry.update(overrides)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def test_cmd_log_renders_the_human_readable_trail(tmp_path, monkeypatch, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(ledger, "LEDGER_PATH", ledger_path)
    _write_entry(ledger_path)

    cli.cmd_log(Namespace(n=20, json=False))

    out = capsys.readouterr().out
    assert "port_trade" in out
    assert 'Q ▸ "your offer [158]?"' in out
    assert "⌨ ▸ «158»" in out
    assert "+230cr (96,553→96,783)" in out


def test_cmd_log_json_mode_dumps_raw_entries(tmp_path, monkeypatch, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(ledger, "LEDGER_PATH", ledger_path)
    _write_entry(ledger_path)

    cli.cmd_log(Namespace(n=20, json=True))

    out = capsys.readouterr().out
    resp = json.loads(out)
    assert resp["ok"] is True
    assert resp["entries"][0]["prompt"] == "your offer [158]?"


def test_cmd_log_honors_n_and_prints_most_recent(tmp_path, monkeypatch, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(ledger, "LEDGER_PATH", ledger_path)
    _write_entry(ledger_path, prompt="first")
    _write_entry(ledger_path, prompt="second")

    cli.cmd_log(Namespace(n=1, json=False))

    out = capsys.readouterr().out
    assert "second" in out
    assert "first" not in out


def test_cmd_log_empty_ledger_prints_placeholder_not_a_crash(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "nope.jsonl")

    cli.cmd_log(Namespace(n=20, json=False))

    out = capsys.readouterr().out
    assert "ledger empty" in out


def test_log_verb_is_wired_in_the_argparser():
    parser = cli.build_parser()
    args = parser.parse_args(["log", "--n", "5"])
    assert args.func is cli.cmd_log
    assert args.n == 5


def test_trail_alias_is_wired_in_the_argparser():
    parser = cli.build_parser()
    args = parser.parse_args(["trail"])
    assert args.func is cli.cmd_log
