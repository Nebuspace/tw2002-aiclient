"""WO-EXPLORE-CLI-INVOKE — CLI wiring for ``tw explore start|stop|status``.

Proves parser wiring, ``send_request`` payload mapping, and exit-code
behaviour against a mocked transport -- no live daemon required.
"""

from __future__ import annotations

import argparse

import pytest

from tw2002_aiclient.session import cli


# ---------------------------------------------------------------------------
# Parser shape
# ---------------------------------------------------------------------------

def test_parser_lists_explore():
    help_text = cli.build_parser().format_help()
    assert "explore" in help_text


def test_explore_help_exits_zero():
    """``tw explore --help`` must exit 0 (SystemExit with code 0)."""
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["explore", "--help"])
    assert exc.value.code == 0


def test_explore_start_help_exits_zero():
    """``tw explore start --help`` must exit 0."""
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["explore", "start", "--help"])
    assert exc.value.code == 0


def test_explore_stop_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["explore", "stop", "--help"])
    assert exc.value.code == 0


def test_explore_status_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["explore", "status", "--help"])
    assert exc.value.code == 0


def test_explore_start_parses_required_world_id():
    args = cli.build_parser().parse_args(["explore", "start", "--world-id", "ona"])
    assert args.func is cli.cmd_explore_start
    assert args.world_id == "ona"
    assert args.min_sectors is None
    assert args.turn_budget is None


def test_explore_start_parses_optional_flags():
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "test",
        "--min-sectors", "10", "--turn-budget", "100",
    ])
    assert args.min_sectors == 10
    assert args.turn_budget == 100


def test_explore_stop_parses():
    args = cli.build_parser().parse_args(["explore", "stop"])
    assert args.func is cli.cmd_explore_stop


def test_explore_status_parses():
    args = cli.build_parser().parse_args(["explore", "status"])
    assert args.func is cli.cmd_explore_status


def test_explore_start_missing_world_id_errors():
    """``tw explore start`` without --world-id is an argparse error (exit 2)."""
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["explore", "start"])
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Payload mapping
# ---------------------------------------------------------------------------

def test_explore_start_sends_world_id_only(monkeypatch):
    """Minimal start: world_id plus the dock arm (default OFF).

    ``dock_new_ports`` and ``fight_tolls`` are always sent so CLI and daemon
    cannot silently disagree (both daemon library defaults are also False).
    WO-EXPLORE-DOCK-DEFAULT-OFF flipped the CLI dock default OFF after a live
    map-fill halt regression; WO-FIGHTER-TOLL-POLICY-WIRE added the combat arm
    already OFF, having learned it there.

    Asserted as exact EQUALITY, not a subset: a new arm appearing in this
    payload must break this test. A subset check would let a future default-ON
    combat flag ride along silently, which is the one thing this shape of test
    is here to prevent.
    """
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["explore", "start", "--world-id", "ona", "--json"])
    rc = args.func(args)
    assert rc == 0
    assert seen["verb"] == "explore_start"
    assert seen["args"] == {
        "world_id": "ona", "dock_new_ports": False, "fight_tolls": False,
    }


def test_explore_start_sends_optional_flags(monkeypatch):
    """Optional flags forwarded when explicitly set."""
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "test",
        "--min-sectors", "3", "--turn-budget", "20", "--json",
    ])
    args.func(args)
    assert seen["args"] == {
        "world_id": "test", "min_sectors": 3, "turn_budget": 20,
        "dock_new_ports": False, "fight_tolls": False,
    }


def test_explore_stop_sends_empty_payload(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["explore", "stop", "--json"])
    rc = args.func(args)
    assert rc == 0
    assert seen["verb"] == "explore_stop"
    assert seen["args"] == {}


def test_explore_status_sends_empty_payload(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["explore", "status", "--json"])
    rc = args.func(args)
    assert rc == 0
    assert seen["verb"] == "explore_status"
    assert seen["args"] == {}


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

def test_explore_start_ok_false_returns_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "send_request",
                        lambda *a, **kw: {"ok": False, "error": "not_running"})
    args = cli.build_parser().parse_args(["explore", "start", "--world-id", "x", "--json"])
    assert args.func(args) != 0


def test_explore_stop_ok_false_returns_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "send_request",
                        lambda *a, **kw: {"ok": False, "error": "not_running"})
    args = cli.build_parser().parse_args(["explore", "stop", "--json"])
    assert args.func(args) != 0


def test_explore_status_ok_false_returns_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "send_request",
                        lambda *a, **kw: {"ok": False, "error": "not_running"})
    args = cli.build_parser().parse_args(["explore", "status", "--json"])
    assert args.func(args) != 0


def test_explore_start_parses_intent_find_formations():
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "ona",
        "--intent", "find_formations",
    ])
    assert args.intent == "find_formations"


def test_explore_start_rejects_unknown_intent():
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([
            "explore", "start", "--world-id", "ona",
            "--intent", "not_a_real_intent",
        ])
    assert exc.value.code == 2


def test_explore_start_sends_intent(monkeypatch):
    seen = {}

    def fake_send(verb, payload, run_dir=None):
        seen["verb"] = verb
        seen["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    monkeypatch.setattr(cli, "print_response", lambda *a, **k: None)
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "ona",
        "--intent", "find_formations",
    ])
    assert args.func(args) == 0
    assert seen["verb"] == "explore_start"
    assert seen["payload"]["intent"] == "find_formations"
    assert seen["payload"]["world_id"] == "ona"


def test_explore_start_help_lists_chain_hunt_required_flags():
    """Both chain-hunt flags must appear as required (no argparse [default: N])."""
    top = cli.build_parser()
    ex = None
    for action in top._actions:
        if isinstance(action, argparse._SubParsersAction):
            ex = action.choices.get("explore")
            break
    assert ex is not None
    start = None
    for action in ex._actions:
        if isinstance(action, argparse._SubParsersAction):
            start = action.choices.get("start")
            break
    assert start is not None
    help_text = start.format_help()
    assert "--exhaust-depth" in help_text
    assert "REQUIRED with --intent chain_hunt" in help_text
    # argparse only emits ``[default: …]`` when default is not None — neither
    # flag invents a numeric default.
    assert "[default:" not in help_text


def test_explore_start_parses_chain_hunt_with_required_flags():
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "ona",
        "--intent", "chain_hunt",
        "--exhaust-depth", "3",
        "--turn-budget", "40",
    ])
    assert args.intent == "chain_hunt"
    assert args.exhaust_depth == 3
    assert args.turn_budget == 40


def test_explore_start_chain_hunt_missing_flags_fail_closed(monkeypatch, capsys):
    sent = []

    def fake_send(*a, **k):
        sent.append(1)
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "ona",
        "--intent", "chain_hunt",
    ])
    rc = args.func(args)
    assert rc == 2
    assert not sent
    err = capsys.readouterr().err
    assert "--turn-budget" in err
    assert "--exhaust-depth" in err


def test_explore_start_sends_chain_hunt_payload(monkeypatch):
    seen = {}

    def fake_send(verb, payload, run_dir=None):
        seen["verb"] = verb
        seen["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(cli, "send_request", fake_send)
    monkeypatch.setattr(cli, "print_response", lambda *a, **k: None)
    args = cli.build_parser().parse_args([
        "explore", "start", "--world-id", "ona",
        "--intent", "chain_hunt",
        "--exhaust-depth", "2",
        "--turn-budget", "25",
    ])
    assert args.func(args) == 0
    assert seen["payload"]["intent"] == "chain_hunt"
    assert seen["payload"]["exhaust_depth"] == 2
    assert seen["payload"]["turn_budget"] == 25
