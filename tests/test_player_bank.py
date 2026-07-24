"""Player bank stub tests (WO-P1-015) — metadata-only list_players.

Live API is thin: list_players() + NEVER/TURNS_UNKNOWN sentinels.
No load_bank/save_bank/add_player/next_player yet. Never touches the
real config/ or state/ trees (BANK_PATH + credentials monkeypatched).
"""

import json

from tw2002_aiclient.session import credentials, player_bank


def _point_bank_at(tmp_path, monkeypatch, body=None):
    bank_path = tmp_path / "player_bank.json"
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    if body is not None:
        bank_path.write_text(json.dumps(body), encoding="utf-8")
    return bank_path


def test_constants_and_paths():
    assert player_bank.NEVER == "never"
    assert player_bank.TURNS_UNKNOWN == "-"
    assert player_bank.STATE_DIR.name == "state"
    assert player_bank.BANK_PATH.name == "player_bank.json"


def test_list_players_empty_when_no_profiles_and_no_bank(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(credentials, "list_profile_summaries", lambda: [])
    assert player_bank.list_players() == []


def test_list_players_joins_profile_with_never_turns_when_bank_empty(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(
        credentials,
        "list_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "server": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    rows = player_bank.list_players()
    assert len(rows) == 1
    assert rows[0] == {
        "name": "alpha",
        "handle": "ALPHAH",
        "host": "alpha.test.example",
        "game_letter": "F",
        "last_played": player_bank.NEVER,
        "turns_state": player_bank.TURNS_UNKNOWN,
    }


def test_list_players_merges_bank_rotation_fields(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {
                    "name": "alpha",
                    "last_played": "2026-07-23T12:00:00Z",
                    "turns_state": "exhausted",
                }
            ],
        },
    )
    monkeypatch.setattr(
        credentials,
        "list_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    rows = player_bank.list_players()
    assert rows[0]["last_played"] == "2026-07-23T12:00:00Z"
    assert rows[0]["turns_state"] == "exhausted"


def test_list_players_surfaces_bank_only_orphan_after_profile_removed(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {
                    "name": "ghost",
                    "handle": "GHOSTH",
                    "host": "old.example",
                    "game_letter": "A",
                    "last_played": "2026-01-01T00:00:00Z",
                    "turns_state": "ok",
                }
            ],
        },
    )
    monkeypatch.setattr(credentials, "list_profile_summaries", lambda: [])
    rows = player_bank.list_players()
    assert len(rows) == 1
    assert rows[0]["name"] == "ghost"
    assert rows[0]["handle"] == "GHOSTH"
    assert rows[0]["last_played"] == "2026-01-01T00:00:00Z"


def test_list_players_skips_profile_rows_with_error(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(
        credentials,
        "list_profile_summaries",
        lambda: [{"name": "broken", "error": "missing host", "handle": "X"}],
    )
    assert player_bank.list_players() == []


def test_list_players_tolerates_corrupt_bank_json(tmp_path, monkeypatch):
    bank_path = tmp_path / "player_bank.json"
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    bank_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        credentials,
        "list_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    rows = player_bank.list_players()
    assert len(rows) == 1
    assert rows[0]["last_played"] == player_bank.NEVER


def test_list_players_never_includes_password_keys(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [{"name": "alpha", "password": "should-never-surface"}],
        },
    )
    monkeypatch.setattr(
        credentials,
        "list_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    row = player_bank.list_players()[0]
    assert "password" not in row
    assert "should-never-surface" not in json.dumps(row)
