---
type: Reference
title: Test Cases — Cli Players
description: `tw players` CLI verb tests -- no daemon involved, direct.
resource: repo://tw2002-aiclient/tests/test_cli_players.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cli_players.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_`tw players` CLI verb tests -- no daemon involved, direct_

| Test | Blurb |
|------|-------|
| `test_cmd_players_list_empty_bank_shows_hint_without_creating_file` | Cmd players list empty bank shows hint without creating file. |
| `test_cmd_players_list_prints_entries_with_never_for_unplayed` | Cmd players list prints entries with never for unplayed. |
| `test_cmd_players_list_shows_last_played_timestamp_when_set` | Cmd players list shows last played timestamp when set. |
| `test_cmd_players_list_json_mode_dumps_raw_entries` | Cmd players list json mode dumps raw entries. |
| `test_cmd_players_add_creates_entry_and_prints_confirmation` | Cmd players add creates entry and prints confirmation. |
| `test_cmd_players_add_with_notes_stores_scalar_values` | Cmd players add with notes stores scalar values. |
| `test_cmd_players_add_duplicate_name_is_a_clean_error_exit_1` | Cmd players add duplicate name is a clean error exit 1. |
| `test_cmd_players_add_unknown_profile_is_a_clean_error_exit_1` | Cmd players add unknown profile is a clean error exit 1. |
| `test_cmd_players_add_rejects_password_shaped_note_key` | Cmd players add rejects password shaped note key. |
| `test_cmd_players_add_bad_note_shape_reports_the_note_flag_not_param` | Cmd players add bad note shape reports the note flag not param. |
| `test_cmd_players_add_never_prints_a_password` | Profile/Profile-derived entries never carry a password field at. |
| `test_cmd_players_next_returns_least_recently_played` | Cmd players next returns least recently played. |
| `test_cmd_players_next_rotates_away_from_current` | Cmd players next rotates away from current. |
| `test_cmd_players_next_all_exhausted_prints_none` | Cmd players next all exhausted prints none. |
| `test_cmd_players_next_empty_bank_prints_none` | Cmd players next empty bank prints none. |
| `test_players_verb_defaults_to_list` | Players verb defaults to list. |
| `test_players_verb_accepts_json` | Players verb accepts json. |
| `test_players_add_subcommand_is_wired` | Players add subcommand is wired. |
| `test_players_next_subcommand_is_wired` | Players next subcommand is wired. |
| `test_players_next_subcommand_current_defaults_to_none` | Players next subcommand current defaults to none. |
