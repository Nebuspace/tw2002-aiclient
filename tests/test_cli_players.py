"""`tw players` CLI verb tests -- no daemon involved, direct
state/player_bank.json access (TW-31 client-side wiring, v1).

Isolation follows the same monkeypatch-the-module-attribute idiom as
tests/test_cli_log.py (which swaps ledger.LEDGER_PATH): here we swap
player_bank.BANK_PATH and credentials.PROFILES_PATH so cmd_players_*
(which call player_bank.load_bank()/add_player()/next_player() with no
explicit path args) never touch the real config/ or state/ directories.
"""

import json
from argparse import Namespace

import pytest

from twclient import cli, credentials, player_bank

_ALPHA_PROFILE = '[alpha]\nhost="alpha.test.example"\nport=23\ngame_letter="F"\nhandle="ALPHAH"\n'
_BRAVO_PROFILE = '[bravo]\nhost="bravo.test.example"\nport=23\ngame_letter="F"\nhandle="BRAVOH"\n'


@pytest.fixture
def bank_path(tmp_path, monkeypatch):
    path = tmp_path / "player_bank.json"
    monkeypatch.setattr(player_bank, "BANK_PATH", path)
    return path


@pytest.fixture
def profiles_path(tmp_path, monkeypatch):
    path = tmp_path / "profiles.toml"
    path.write_text(_ALPHA_PROFILE + _BRAVO_PROFILE, encoding="utf-8")
    monkeypatch.setattr(credentials, "PROFILES_PATH", path)
    return path


# -- players (list) -----------------------------------------------------

def test_cmd_players_list_empty_bank_shows_hint_without_creating_file(bank_path, capsys):
    cli.cmd_players_list(Namespace(json=False))

    out = capsys.readouterr().out
    assert "tw players add" in out
    assert not bank_path.exists()  # listing an absent bank must never create it


def test_cmd_players_list_prints_entries_with_never_for_unplayed(bank_path, profiles_path, capsys):
    player_bank.add_player("alpha", bank_path=bank_path, profiles_path=profiles_path)

    cli.cmd_players_list(Namespace(json=False))

    out = capsys.readouterr().out
    assert "alpha" in out
    assert "ALPHAH" in out
    assert "alpha.test.example" in out
    assert "never" in out


def test_cmd_players_list_shows_last_played_timestamp_when_set(bank_path, profiles_path, capsys):
    player_bank.add_player("alpha", bank_path=bank_path, profiles_path=profiles_path)
    player_bank.mark_played("alpha", bank_path=bank_path)

    cli.cmd_players_list(Namespace(json=False))

    out = capsys.readouterr().out
    assert "never" not in out


def test_cmd_players_list_json_mode_dumps_raw_entries(bank_path, profiles_path, capsys):
    player_bank.add_player("alpha", bank_path=bank_path, profiles_path=profiles_path)

    cli.cmd_players_list(Namespace(json=True))

    out = capsys.readouterr().out
    resp = json.loads(out)
    assert resp["ok"] is True
    assert resp["players"][0]["name"] == "alpha"
    assert resp["players"][0]["handle"] == "ALPHAH"


# -- players add ----------------------------------------------------------

def test_cmd_players_add_creates_entry_and_prints_confirmation(bank_path, profiles_path, capsys):
    cli.cmd_players_add(Namespace(profile="alpha", note=[]))

    out = capsys.readouterr().out
    assert "added alpha (ALPHAH)" in out
    bank = player_bank.load_bank(bank_path=bank_path)
    assert bank["players"][0]["name"] == "alpha"
    assert bank["players"][0]["handle"] == "ALPHAH"


def test_cmd_players_add_with_notes_stores_scalar_values(bank_path, profiles_path):
    cli.cmd_players_add(Namespace(profile="alpha", note=["role=trader", "priority=1"]))

    bank = player_bank.load_bank(bank_path=bank_path)
    assert bank["players"][0]["notes"] == {"role": "trader", "priority": "1"}


def test_cmd_players_add_duplicate_name_is_a_clean_error_exit_1(bank_path, profiles_path, capsys):
    cli.cmd_players_add(Namespace(profile="alpha", note=[]))
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_players_add(Namespace(profile="alpha", note=[]))

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert out.startswith("ERROR:")
    # still exactly one entry -- the failed re-add must not have appended a dupe
    assert len(player_bank.load_bank(bank_path=bank_path)["players"]) == 1


def test_cmd_players_add_unknown_profile_is_a_clean_error_exit_1(bank_path, profiles_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_players_add(Namespace(profile="nonexistent", note=[]))

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert out.startswith("ERROR:")


def test_cmd_players_add_rejects_password_shaped_note_key(bank_path, profiles_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_players_add(Namespace(profile="alpha", note=["password=hunter2"]))

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert out.startswith("ERROR:")
    assert "hunter2" not in out  # rejected note VALUE must never be echoed
    # bank must not have been created/mutated by the rejected add
    assert player_bank.load_bank(bank_path=bank_path)["players"] == []


def test_cmd_players_add_bad_note_shape_reports_the_note_flag_not_param(bank_path, profiles_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_players_add(Namespace(profile="alpha", note=["not-a-kv-pair"]))

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "--note must be k=v" in out


def test_cmd_players_add_never_prints_a_password(bank_path, profiles_path, capsys):
    """Profile/Profile-derived entries never carry a password field at
    all (credentials.Profile has none) -- confirm the confirmation line
    only ever surfaces name/handle, nothing password-shaped."""
    cli.cmd_players_add(Namespace(profile="alpha", note=[]))

    out = capsys.readouterr().out
    assert "password" not in out.lower()
    assert "secret" not in out.lower()


# -- players next -----------------------------------------------------------

def test_cmd_players_next_returns_least_recently_played(bank_path, profiles_path, capsys):
    player_bank.add_player("alpha", bank_path=bank_path, profiles_path=profiles_path)
    player_bank.add_player("bravo", bank_path=bank_path, profiles_path=profiles_path)
    player_bank.mark_played("alpha", bank_path=bank_path)

    cli.cmd_players_next(Namespace(current=None))

    out = capsys.readouterr().out.strip()
    assert out == "bravo"  # never-played sorts ahead of a real timestamp


def test_cmd_players_next_rotates_away_from_current(bank_path, profiles_path, capsys):
    player_bank.add_player("alpha", bank_path=bank_path, profiles_path=profiles_path)
    player_bank.add_player("bravo", bank_path=bank_path, profiles_path=profiles_path)

    cli.cmd_players_next(Namespace(current="alpha"))

    out = capsys.readouterr().out.strip()
    assert out == "bravo"


def test_cmd_players_next_all_exhausted_prints_none(bank_path, profiles_path, capsys):
    player_bank.add_player("alpha", bank_path=bank_path, profiles_path=profiles_path)
    player_bank.mark_played("alpha", turns_state="exhausted", bank_path=bank_path)

    cli.cmd_players_next(Namespace(current=None))

    out = capsys.readouterr().out.strip()
    assert out == "none: all players exhausted"


def test_cmd_players_next_empty_bank_prints_none(bank_path, capsys):
    cli.cmd_players_next(Namespace(current=None))

    out = capsys.readouterr().out.strip()
    assert out == "none: all players exhausted"


# -- argparse wiring ----------------------------------------------------

def test_players_verb_defaults_to_list():
    parser = cli.build_parser()
    args = parser.parse_args(["players"])
    assert args.func is cli.cmd_players_list
    assert args.players_action is None


def test_players_verb_accepts_json():
    parser = cli.build_parser()
    args = parser.parse_args(["players", "--json"])
    assert args.func is cli.cmd_players_list
    assert args.json is True


def test_players_add_subcommand_is_wired():
    parser = cli.build_parser()
    args = parser.parse_args(["players", "add", "alpha", "--note", "role=trader"])
    assert args.func is cli.cmd_players_add
    assert args.profile == "alpha"
    assert args.note == ["role=trader"]


def test_players_next_subcommand_is_wired():
    parser = cli.build_parser()
    args = parser.parse_args(["players", "next", "--current", "alpha"])
    assert args.func is cli.cmd_players_next
    assert args.current == "alpha"


def test_players_next_subcommand_current_defaults_to_none():
    parser = cli.build_parser()
    args = parser.parse_args(["players", "next"])
    assert args.func is cli.cmd_players_next
    assert args.current is None
