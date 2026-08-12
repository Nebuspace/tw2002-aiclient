"""``tw players add`` — thin wrapper over ``credentials.create_profile``."""

from __future__ import annotations

from tw2002_aiclient import players_cli
from tw2002_aiclient.session import cli, credentials


def test_tw_players_add_wires_to_cmd() -> None:
    args = cli.build_parser().parse_args(
        ["players", "add", "--server", "demo", "--game-letter", "A", "--handle", "Pilot"]
    )
    assert args.func is players_cli.cmd_players_add


def test_cmd_players_add_prints_section(monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def fake_create_profile(**kwargs):
        calls.append(kwargs)
        return "pilot"

    monkeypatch.setattr(credentials, "create_profile", fake_create_profile)
    args = cli.build_parser().parse_args(
        [
            "players",
            "add",
            "--server",
            "demo",
            "--game-letter",
            "B",
            "--handle",
            "Pilot",
            "--profile",
            "custom",
        ]
    )
    assert players_cli.cmd_players_add(args) == 0
    assert calls == [
        {
            "server": "demo",
            "game_letter": "B",
            "handle": "Pilot",
            "name": "custom",
        }
    ]
    assert capsys.readouterr().out.strip() == "pilot"


def test_cmd_players_add_value_error_exits_1(monkeypatch, capsys) -> None:
    def boom(**_kwargs):
        raise ValueError("unknown server catalog key: 'nope'")

    monkeypatch.setattr(credentials, "create_profile", boom)
    args = cli.build_parser().parse_args(
        ["players", "add", "--server", "nope", "--game-letter", "A", "--handle", "X"]
    )
    assert players_cli.cmd_players_add(args) == 1
    err = capsys.readouterr().err
    assert "unknown server catalog key" in err
