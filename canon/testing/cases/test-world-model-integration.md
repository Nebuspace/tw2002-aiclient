---
type: Reference
title: Test Cases — World Model Integration
description: End-to-end proof that the TW-06/TW-25 world-model foundation is.
resource: repo://tw2002-aiclient/tests/test_world_model_integration.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_world_model_integration.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_End-to-end proof that the TW-06/TW-25 world-model foundation is_

| Test | Blurb |
|------|-------|
| `test_do_with_a_sector_screen_persists_the_sector_queryable` | Do with a sector screen persists the sector queryable. |
| `test_two_worlds_stay_isolated_by_profile_handle` | Two worlds stay isolated by profile handle. |
| `test_cim_report_screen_bulk_upserts_every_sector` | Cim report screen bulk upserts every sector. |
| `test_help_screen_quoting_a_cim_report_is_not_ingested` | Adapted from mack's probe_poison. |
| `test_forged_chat_broadcast_quoting_a_cim_report_is_not_ingested` | Adapted from mack's probe_poison. |
| `test_real_sector_wins_over_a_same_screen_phantom_chat_mention_end_to_end` | Adapted from mack's probe_f2_combined. |
| `test_residual_line_isolated_forgery_in_a_narrative_block_is_not_ingested_end_to_end` | Adapted from mack's probe_residual_line_anchor. |
| `test_genuine_sector_screen_with_warps_sibling_persists_correctly` | A plain, non-adversarial genuine sector-status screen using the. |
| `test_genuine_sector_screen_with_full_paren_wrapped_warps_persists_all_six` | WO-FA1 end-to-end propagation proof: the REAL live-server warps. |
| `test_chat_only_screen_with_no_genuine_status_line_persists_nothing` | Adapted from mack's probe_f2_carveout. |
| `test_no_auto_login_profile_no_ops_the_write_hook_cleanly` | No auto login profile no ops the write hook cleanly. |
| `test_a_world_model_write_failure_never_fails_the_do_response` | A world model write failure never fails the do response. |
| `test_a_world_model_write_failure_is_logged_when_the_session_has_a_logger` | Adapted from mack's probe_silent_loss. |
| `test_a_world_model_write_failure_with_no_session_logger_stays_a_clean_noop` | The bare fake-session test doubles that predate `. |
| `test_state_verb_persists_the_observed_sector` | `tw state` observes the current sector exactly like `do`/`read`/. |
| `test_state_verb_also_bulk_ingests_a_genuine_cim_report` | State verb also bulk ingests a genuine cim report. |
| `test_docked_commerce_report_writes_port_to_its_own_command_prompt_sector` | The full FA2b chain, single dispatch: a docked commerce-report. |
| `test_forged_narrative_commodity_mention_does_not_write_port_data` | A screen merely NAMING commodities in narrative text -- no genuine. |
| `test_docked_commerce_report_with_no_command_prompt_sector_writes_nothing` | A genuine commerce report with no trailing Command [TL=. |
| `test_scroll_off_burst_writes_port_to_the_current_sector_not_a_stale_one` | CRITICAL repro (mack, WO-FA2b REVISE): pyte is `pyte. |
| `test_game_knowledge_imports_and_coexists_with_no_write_hook_this_wave` | TW-25's game_knowledge store has no live write-hook this wave --. |
