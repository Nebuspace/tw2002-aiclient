---
type: Reference
title: Test Cases — Player Bank
description: Player bank stub tests (WO-P1-015) — metadata-only list_players.
resource: repo://tw2002-aiclient/tests/test_player_bank.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_player_bank.py`

_Player bank stub tests (WO-P1-015) — metadata-only list_players._

| Test | Blurb |
|------|-------|
| `test_constants_and_paths` | Constants and paths. |
| `test_list_players_empty_when_no_profiles_and_no_bank` | List players empty when no profiles and no bank. |
| `test_list_players_joins_profile_with_never_turns_when_bank_empty` | List players joins profile with never turns when bank empty. |
| `test_list_players_merges_bank_rotation_fields` | List players merges bank rotation fields. |
| `test_list_players_surfaces_bank_only_orphan_after_profile_removed` | List players surfaces bank only orphan after profile removed. |
| `test_list_players_skips_profile_rows_with_error` | List players skips profile rows with error. |
| `test_list_players_tolerates_corrupt_bank_json` | List players tolerates corrupt bank json. |
| `test_list_players_never_includes_password_keys` | List players never includes password keys. |
