"""``tw log`` / ``tw trail`` — trace-ledger trail renderer (WO-WIRE-CLI-LOG-TRAIL-VERB)."""

from __future__ import annotations

import json

from tw2002_aiclient.session import cli
from tw2002_aiclient import mine_cli
from tw2002_aiclient import players_cli
from tw2002_aiclient import planet_colonization_cli
from tw2002_aiclient import port_floor_cli


# Keep in sync with README Verb reference (shipped) + cli.build_parser().
_SHIPPED_VERBS = frozenset(
    {
        "status",
        "ensure",
        "screen",
        "state",
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
        # WO-BUILD-TRADE-CHAIN-CLI-VERB — arm live trade_chain_* RPC.
        "chain",
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
        # WO-BUILD-PLAYER-ROTATION-SELECTOR — read-only next_player surface.
        "players",
        # WO-BUILD-WIRE-TW-MINE-CLI-VERB — ledger candidate mining.
        "mine",
        "patterns",
        # WO-WIRE-MINED-SKILLS-PROMOTE-CLI — promote mined drafts (tw skill approve).
        "skill",
        # WO-BUILD-AI-TEACHER-ANALYZE-CLI — on-demand retrospective AI teacher.
        "teach",
        # WO-BUILD-PORT-FLOOR-PRICE-LIVE-CAPTURE — filesystem observation store.
        "port-floor",
        # WO-BUILD-PLANET-COLONIZATION-LIVE-CAPTURE — planet production observation store.
        "planet-colonization",
        # WO-WIRE-STRATEGY-CARD-TRADEOFFS-OKF-REFS — full authored strategy card
        # (tradeoffs/okf_refs) beyond the width-budgeted DECISIONS renderer.
        "coach",
        # WO-BUILD-CLI-VERBS-FRAMES — settle-frame post-mortem over state/frames/.
        "frames",
    }
)


def test_parser_shipped_verb_allowlist():
    parser = cli.build_parser()
    status = parser.parse_args(["status"])
    ensure = parser.parse_args(["ensure", "--profile", "x"])
    screen = parser.parse_args(["screen"])
    state = parser.parse_args(["state"])
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
    assert state.func is cli.cmd_state
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
    players_next = parser.parse_args(["players", "next"])
    assert players_next.func is players_cli.cmd_players_next
    players_list = parser.parse_args(["players", "list"])
    assert players_list.func is players_cli.cmd_players_list
    players_add = parser.parse_args(
        ["players", "add", "--server", "demo", "--game-letter", "A", "--handle", "Pilot"]
    )
    assert players_add.func is players_cli.cmd_players_add
    mine = parser.parse_args(["mine", "--no-propose"])
    patterns = parser.parse_args(["patterns", "--top-k", "1"])
    assert mine.func is mine_cli.cmd_mine
    assert patterns.func is mine_cli.cmd_mine
    assert patterns.top_k == 1
    from tw2002_aiclient import skill_cli

    skill_approve = parser.parse_args(["skill", "approve", "mined-0-demo"])
    assert skill_approve.func is skill_cli.cmd_skill_approve
    assert skill_approve.name == "mined-0-demo"
    port_floor_snap = parser.parse_args(
        ["port-floor", "snapshot", "--world-dir", "x"]
    )
    assert port_floor_snap.func is port_floor_cli.cmd_port_floor_snapshot
    port_floor_an = parser.parse_args(["port-floor", "analyze"])
    assert port_floor_an.func is port_floor_cli.cmd_port_floor_analyze
    planet_col_snap = parser.parse_args(
        ["planet-colonization", "snapshot", "--planet-dir", "x"]
    )
    assert planet_col_snap.func is planet_colonization_cli.cmd_planet_colonization_snapshot
    planet_col_an = parser.parse_args(["planet-colonization", "analyze"])
    assert planet_col_an.func is planet_colonization_cli.cmd_planet_colonization_analyze
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
