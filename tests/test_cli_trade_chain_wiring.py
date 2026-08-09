"""WO-BUILD-TRADE-CHAIN-CLI-VERB — CLI wiring for ``tw chain start|stop|status``.

Proves parser wiring, ``send_request`` payload mapping, and exit-code
behaviour against a mocked transport — no live daemon required.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import cli
from tw2002_aiclient.session.trade_chain import (
    DEFAULT_CASH_FLOOR,
    DEFAULT_TURN_RESERVE,
)


def test_parser_lists_chain():
    help_text = cli.build_parser().format_help()
    assert "chain" in help_text


def test_chain_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["chain", "--help"])
    assert exc.value.code == 0


@pytest.mark.parametrize("sub", ["start", "stop", "status"])
def test_chain_sub_help_exits_zero(sub):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["chain", sub, "--help"])
    assert exc.value.code == 0


def test_chain_start_parses_required():
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "academy",
        "--fingerprint", "abc123",
    ])
    assert args.func is cli.cmd_chain_start
    assert args.world_id == "academy"
    assert args.fingerprint == "abc123"
    assert args.cash_floor == DEFAULT_CASH_FLOOR
    assert args.turn_reserve == DEFAULT_TURN_RESERVE


def test_chain_start_parses_optional_floors():
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "academy",
        "--fingerprint", "fp",
        "--cash-floor", "5000",
        "--turn-reserve", "25",
    ])
    assert args.cash_floor == 5000
    assert args.turn_reserve == 25


def test_chain_start_missing_fingerprint_errors():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([
            "chain", "start", "--world-id", "academy",
        ])
    assert exc.value.code == 2


def test_chain_start_missing_world_id_errors():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([
            "chain", "start", "--fingerprint", "fp",
        ])
    assert exc.value.code == 2


def test_chain_stop_parses():
    args = cli.build_parser().parse_args(["chain", "stop"])
    assert args.func is cli.cmd_chain_stop


def test_chain_status_parses():
    args = cli.build_parser().parse_args(["chain", "status"])
    assert args.func is cli.cmd_chain_status


def test_chain_start_sends_defaults(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "academy",
        "--fingerprint", "fp1",
        "--json",
    ])
    rc = args.func(args)
    assert rc == 0
    assert seen["verb"] == "trade_chain_start"
    assert seen["args"] == {
        "world_id": "academy",
        "fingerprint": "fp1",
        "cash_floor": DEFAULT_CASH_FLOOR,
        "turn_reserve": DEFAULT_TURN_RESERVE,
    }


def test_chain_start_sends_optional_floors(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "w",
        "--fingerprint", "f",
        "--cash-floor", "2000",
        "--turn-reserve", "15",
        "--json",
    ])
    args.func(args)
    assert seen["args"] == {
        "world_id": "w",
        "fingerprint": "f",
        "cash_floor": 2000,
        "turn_reserve": 15,
    }


def test_chain_stop_sends_empty_payload(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["chain", "stop", "--json"])
    assert args.func(args) == 0
    assert seen["verb"] == "trade_chain_stop"
    assert seen["args"] == {}


def test_chain_status_sends_empty_payload(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["chain", "status", "--json"])
    assert args.func(args) == 0
    assert seen["verb"] == "trade_chain_status"
    assert seen["args"] == {}


def test_chain_start_ok_false_returns_nonzero(monkeypatch):
    monkeypatch.setattr(
        cli,
        "send_request",
        lambda *a, **kw: {"ok": False, "error": "trade_chain_unavailable"},
    )
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "x",
        "--fingerprint", "y",
        "--json",
    ])
    assert args.func(args) != 0


def test_chain_start_parses_profit_target_and_pass_count():
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "academy",
        "--fingerprint", "fp",
        "--profit-target", "5000",
        "--pass-count", "7",
    ])
    assert args.profit_target == 5000
    assert args.pass_count == 7


def test_chain_start_bare_pass_count_defaults_to_ten():
    from tw2002_aiclient.session.trade_chain import DEFAULT_PASS_COUNT

    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "academy",
        "--fingerprint", "fp",
        "--pass-count",
    ])
    assert args.pass_count == DEFAULT_PASS_COUNT == 10


def test_chain_start_sends_profit_target_and_pass_count(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args([
        "chain", "start",
        "--world-id", "w",
        "--fingerprint", "f",
        "--profit-target", "9000",
        "--pass-count", "4",
        "--json",
    ])
    args.func(args)
    assert seen["args"]["profit_target"] == 9000
    assert seen["args"]["pass_count"] == 4
    assert "cash_floor" in seen["args"]
