"""``tw players rotate`` — rotation driver CLI (WO-BUILD-PLAYER-BANK-ROTATION-DRIVER)."""

from __future__ import annotations

from datetime import datetime, timezone

from tw2002_aiclient import players_cli
from tw2002_aiclient.session import cli, player_bank


def test_tw_players_rotate_wires_to_cmd() -> None:
    args = cli.build_parser().parse_args(["players", "rotate"])
    assert args.func is players_cli.cmd_players_rotate


def test_cmd_players_rotate_prints_due_name(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        player_bank,
        "list_players",
        lambda: [{"name": "alpha", "last_played": "never"}],
    )
    args = cli.build_parser().parse_args(["players", "rotate"])
    assert players_cli.cmd_players_rotate(args) == 0
    out = capsys.readouterr().out
    assert out.strip() == "alpha"


def test_cmd_players_rotate_none_eligible_exits_1(monkeypatch, capsys) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        player_bank,
        "list_players",
        lambda: [{"name": "alpha", "last_played": now.isoformat()}],
    )
    args = cli.build_parser().parse_args(["players", "rotate"])
    assert players_cli.cmd_players_rotate(args) == 1
    out = capsys.readouterr().out
    assert "no eligible player" in out
    assert "cooling down" in out


def test_cmd_players_rotate_empty_bank_exits_1(monkeypatch, capsys) -> None:
    monkeypatch.setattr(player_bank, "list_players", lambda: [])
    args = cli.build_parser().parse_args(["players", "rotate"])
    assert players_cli.cmd_players_rotate(args) == 1
    out = capsys.readouterr().out
    assert "empty bank" in out


def test_cmd_players_rotate_unreadable_exits_2(monkeypatch, capsys) -> None:
    def boom():
        raise player_bank.BankUnreadable("corrupt", "invalid JSON", "/tmp/x")

    monkeypatch.setattr(player_bank, "list_players", boom)
    args = cli.build_parser().parse_args(["players", "rotate"])
    assert players_cli.cmd_players_rotate(args) == 2
    err = capsys.readouterr().err
    assert "unreadable" in err


def test_cmd_players_rotate_never_calls_advance_rotations_default_lookup(
    monkeypatch, capsys
) -> None:
    """cmd_players_rotate passes the already-read rows through, never a second read."""
    calls: list[object] = []
    real_advance = player_bank.advance_rotation

    def spy(rows=None, **kwargs):
        calls.append(rows)
        return real_advance(rows, **kwargs)

    monkeypatch.setattr(
        player_bank,
        "list_players",
        lambda: [{"name": "alpha", "last_played": "never"}],
    )
    monkeypatch.setattr(player_bank, "advance_rotation", spy)
    args = cli.build_parser().parse_args(["players", "rotate"])
    assert players_cli.cmd_players_rotate(args) == 0
    assert calls == [[{"name": "alpha", "last_played": "never"}]]
