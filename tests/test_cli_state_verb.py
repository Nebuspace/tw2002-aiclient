"""WO-BUILD-CLI-STATE-VERB-SUBPARSER — ``tw state`` wraps protocol ``state``."""

from __future__ import annotations

import json
from argparse import Namespace

from tw2002_aiclient.session import cli


def test_parser_lists_state():
    parser = cli.build_parser()
    help_text = parser.format_help()
    assert "state" in help_text
    args = parser.parse_args(["state", "--json", "--run-dir", "run/ona"])
    assert args.func is cli.cmd_state
    assert args.json is True
    assert args.run_dir == "run/ona"


def test_cmd_state_forwards_empty_args_and_run_dir(monkeypatch, capsys, tmp_path):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        seen["run_dir"] = run_dir
        return {
            "ok": True,
            "state": {"sector": {"outcome": "read", "sector": 42, "source": "command_prompt"}},
            "classification": "main_command",
            "connected": True,
        }

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = Namespace(json=True, run_dir=str(tmp_path / "ona"))
    rc = cli.cmd_state(args)
    assert rc == 0
    assert seen["verb"] == "state"
    assert seen["args"] == {}
    assert seen["run_dir"] == tmp_path / "ona"
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"]["sector"]["sector"] == 42


def test_cmd_state_nonzero_on_error(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "send_request",
        lambda *a, **k: {"ok": False, "error": "daemon_unreachable"},
    )
    rc = cli.cmd_state(Namespace(json=True, run_dir=None))
    assert rc == 1
    assert "daemon_unreachable" in capsys.readouterr().out
