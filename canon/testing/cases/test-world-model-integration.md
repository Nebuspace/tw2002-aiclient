---
type: Reference
title: Test Cases — test_world_model_integration
description: World model integration.
resource: repo://tw2002-aiclient/tests/test_world_model_integration.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_world_model_integration.py`

_World model integration._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_do_with_a_sector_screen_persists_the_sector_queryable` | Do with a sector screen persists the sector queryable. |
| `test_two_worlds_stay_isolated_by_profile_handle` | Two worlds stay isolated by profile handle. |
| `test_cim_report_screen_bulk_upserts_every_sector` | Cim report screen bulk upserts every sector. |
| `test_help_screen_quoting_a_cim_report_is_not_ingested` | Help screen quoting a cim report is not ingested. |
| `test_forged_chat_broadcast_quoting_a_cim_report_is_not_ingested` | Adapted from mack's probe_poison.py Scenario B: a forged/griefing chat broadcast reproducing the identical report punctuation must not get ingested either. |
| `test_real_sector_wins_over_a_same_screen_phantom_chat_mention_end_to_end` | Real sector wins over a same screen phantom chat mention end to end. |
| `test_residual_line_isolated_forgery_in_a_narrative_block_is_not_ingested_end_to_end` | Residual line isolated forgery in a narrative block is not ingested end to end. |
| `test_genuine_sector_screen_with_warps_sibling_persists_correctly` | Genuine sector screen with warps sibling persists correctly. |
| `test_genuine_sector_screen_with_full_paren_wrapped_warps_persists_all_six` | Genuine sector screen with full paren wrapped warps persists all six. |
| `test_chat_only_screen_with_no_genuine_status_line_persists_nothing` | Chat only screen with no genuine status line persists nothing. |
| `test_no_auto_login_profile_no_ops_the_write_hook_cleanly` | No auto login profile no ops the write hook cleanly. |
| `test_a_world_model_write_failure_never_fails_the_do_response` | A world model write failure never fails the do response. |
| `test_a_world_model_write_failure_is_logged_when_the_session_has_a_logger` | A world model write failure is logged when the session has a logger. |
| `test_a_world_model_write_failure_with_no_session_logger_stays_a_clean_noop` | A world model write failure with no session logger stays a clean noop. |
| `test_state_verb_persists_the_observed_sector` | State verb persists the observed sector. |
| `test_state_verb_also_bulk_ingests_a_genuine_cim_report` | State verb also bulk ingests a genuine cim report. |
| `test_docked_commerce_report_writes_port_to_its_own_command_prompt_sector` | Docked commerce report writes port to its own command prompt sector. |
| `test_forged_narrative_commodity_mention_does_not_write_port_data` | Forged narrative commodity mention does not write port data. |
| `test_docked_commerce_report_with_no_command_prompt_sector_writes_nothing` | Docked commerce report with no command prompt sector writes nothing. |
| `test_scroll_off_burst_writes_port_to_the_current_sector_not_a_stale_one` | Scroll off burst writes port to the current sector not a stale one. |
| `test_game_knowledge_imports_and_coexists_with_no_write_hook_this_wave` | TW-25's game_knowledge store has no live write-hook this wave -- its filler (the menu-crawler/introspector) is safety-gated and not built yet. |
