"""``tw players list`` — boundary lines + bank rows (WO-BUILD-TW-PLAYERS-LIST)."""

from __future__ import annotations

from tw2002_aiclient import players_cli
from tw2002_aiclient.screens import BANK_EMPTY_LINE, BOUNDARY_LINE_1, BOUNDARY_LINE_2
from tw2002_aiclient.session import cli, player_bank


def test_tw_players_list_wires_to_cmd() -> None:
    args = cli.build_parser().parse_args(["players", "list"])
    assert args.func is players_cli.cmd_players_list


def test_cmd_players_list_prints_boundary_and_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(player_bank, "list_players", lambda: [
        {
            "name": "alpha",
            "handle": "Alpha",
            "host": "local-bbs",
            "game_letter": "A",
            "last_played": "never",
            "turns_state": "-",
        }
    ])
    args = cli.build_parser().parse_args(["players", "list"])
    assert players_cli.cmd_players_list(args) == 0
    out = capsys.readouterr().out
    assert BOUNDARY_LINE_1 in out
    assert BOUNDARY_LINE_2 in out
    assert out.index(BOUNDARY_LINE_1) < out.index("alpha")
    assert "alpha" in out
    assert "local-bbs" in out


def test_cmd_players_list_empty_uses_bank_empty_line(monkeypatch, capsys):
    monkeypatch.setattr(player_bank, "list_players", lambda: [])
    args = cli.build_parser().parse_args(["players", "list"])
    assert players_cli.cmd_players_list(args) == 0
    out = capsys.readouterr().out
    assert BOUNDARY_LINE_1 in out
    assert BANK_EMPTY_LINE in out


def test_cmd_players_list_unreadable_exits_2(monkeypatch, capsys):
    def boom():
        raise player_bank.BankUnreadable("io", "corrupt", "/tmp/x")

    monkeypatch.setattr(player_bank, "list_players", boom)
    args = cli.build_parser().parse_args(["players", "list"])
    assert players_cli.cmd_players_list(args) == 2
    err = capsys.readouterr().err
    assert "unreadable" in err


def test_cmd_players_list_marks_the_rotation_due_row(monkeypatch, capsys):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        player_bank,
        "list_players",
        lambda: [
            {"name": "alpha", "handle": "A", "host": "h", "game_letter": "A",
             "last_played": now.isoformat(), "turns_state": "-"},
            {"name": "bravo", "handle": "B", "host": "h", "game_letter": "A",
             "last_played": "never", "turns_state": "-"},
        ],
    )
    args = cli.build_parser().parse_args(["players", "list"])
    assert players_cli.cmd_players_list(args) == 0
    out = capsys.readouterr().out
    bravo_line = next(ln for ln in out.splitlines() if "bravo" in ln)
    alpha_line = next(ln for ln in out.splitlines() if "alpha" in ln)
    assert bravo_line.startswith("→")
    assert not alpha_line.startswith("→")


def test_cmd_players_list_no_marker_when_all_in_cooldown(monkeypatch, capsys):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        player_bank,
        "list_players",
        lambda: [
            {"name": "alpha", "handle": "A", "host": "h", "game_letter": "A",
             "last_played": now.isoformat(), "turns_state": "-"},
        ],
    )
    args = cli.build_parser().parse_args(["players", "list"])
    assert players_cli.cmd_players_list(args) == 0
    out = capsys.readouterr().out
    alpha_line = next(ln for ln in out.splitlines() if "alpha" in ln)
    assert not alpha_line.startswith("→")


def test_cmd_players_list_marks_broken_profile(monkeypatch, capsys):
    monkeypatch.setattr(
        player_bank,
        "list_players",
        lambda: [
            {
                "name": "broken",
                "handle": "?",
                "host": "?",
                "game_letter": "?",
                "last_played": "never",
                "turns_state": "-",
                "error": "bad toml",
            }
        ],
    )
    args = cli.build_parser().parse_args(["players", "list"])
    assert players_cli.cmd_players_list(args) == 0
    out = capsys.readouterr().out
    assert "broken!" in out
    assert "error: bad toml" in out
