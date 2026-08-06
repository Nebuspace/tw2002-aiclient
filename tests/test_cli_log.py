"""``tw log`` / ``tw trail`` — trace-ledger trail renderer (WO-WIRE-CLI-LOG-TRAIL-VERB)."""

from __future__ import annotations

import json

from tw2002_aiclient.session import cli


# Keep in sync with README Verb reference (shipped) + cli.build_parser().
_SHIPPED_VERBS = frozenset(
    {
        "status",
        "ensure",
        "screen",
        "stop",
        "do",
        "send",
        "read",
        "history",
        "watch",
        "attach",
        "menumap",
        "loops",
        "record",
        "explore",
        "pairs",
        "chains",
        "reflex",
        "rule",
        # WO-WIRE-CLI-LOG-TRAIL-VERB — filesystem trail over state/ledger.jsonl.
        "log",
        "trail",
        # WO-BUILD-POST-SESSION-ACTION-REPORT — app-action digest.
        "report",
        # WO-BUILD-SERVERS-PROBE-CLI-VERBS — inventory summarize + TCP probe.
        "servers",
        "probe",
    }
)


def test_parser_shipped_verb_allowlist():
    parser = cli.build_parser()
    status = parser.parse_args(["status"])
    ensure = parser.parse_args(["ensure", "--profile", "x"])
    screen = parser.parse_args(["screen"])
    stop = parser.parse_args(["stop"])
    do = parser.parse_args(["do", "d"])
    send = parser.parse_args(["send", "x"])
    read = parser.parse_args(["read"])
    history = parser.parse_args(["history"])
    watch = parser.parse_args(["watch"])
    attach = parser.parse_args(["attach"])
    menumap = parser.parse_args(["menumap", "--path", "x"])
    loops = parser.parse_args(["loops"])
    log = parser.parse_args(["log"])
    trail = parser.parse_args(["trail", "--n", "5"])
    assert status.func is cli.cmd_status
    assert ensure.func is cli.cmd_ensure
    assert screen.func is cli.cmd_screen
    assert stop.func is cli.cmd_stop
    assert do.func is cli.cmd_do
    assert send.func is cli.cmd_send
    assert read.func is cli.cmd_read
    assert history.func is cli.cmd_history
    assert watch.func is cli.cmd_watch
    assert attach.func is cli.cmd_attach
    assert menumap.func is cli.cmd_menumap
    assert loops.func is cli.cmd_loops
    assert log.func is cli.cmd_log
    assert trail.func is cli.cmd_log
    assert trail.n == 5
    sub = next(
        a for a in parser._actions if getattr(a, "choices", None) is not None
    )
    assert set(sub.choices) == set(_SHIPPED_VERBS)


def test_log_renders_trail_lines(tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    rows = [
        {
            "ts": "2026-08-05T07:08:45Z",
            "settled_class": "port_trade",
            "prompt": "your offer [158]?",
            "input": "158",
            "reward": {"d_credits": 230},
            "pre_state": {"credits": 96553},
            "post_state": {"credits": 96783},
        },
        {
            "ts": "2026-08-05T07:09:01Z",
            "settled_class": "main_command",
            "prompt": "Command [TL=…]:",
            "input": "D",
            "reward": {},
        },
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    args = cli.build_parser().parse_args(["log", "--ledger", str(ledger), "--n", "1"])
    assert cli.cmd_log(args) == 0
    out = capsys.readouterr().out
    assert "main_command" in out
    assert "port_trade" not in out  # --n 1 → most recent only


def test_trail_alias_same_handler(tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "ts": "2026-08-05T07:08:45Z",
                "settled_class": "port_trade",
                "prompt": "x",
                "input": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    args = cli.build_parser().parse_args(["trail", "--ledger", str(ledger)])
    assert args.func is cli.cmd_log
    assert cli.cmd_log(args) == 0
    assert "port_trade" in capsys.readouterr().out


def test_log_missing_ledger_is_empty_ok(tmp_path, capsys):
    missing = tmp_path / "nope.jsonl"
    args = cli.build_parser().parse_args(["log", "--ledger", str(missing)])
    assert cli.cmd_log(args) == 0
    assert capsys.readouterr().out == ""
