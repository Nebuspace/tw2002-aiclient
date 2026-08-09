---
type: Reference
title: Test Cases — test_protocol_trainer_panel
description: REMOVED — historical inventory; tip module absent. Protocol trainer panel.
resource: repo://tw2002-aiclient/tests/test_protocol_trainer_panel.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_protocol_trainer_panel.py`

_Protocol trainer panel._

> **REMOVED** — module absent on tip (not merely pytest-ignored). Catalogued for completeness (historical inventory).
| Test | Blurb |
|------|-------|
| `test_list_skills_empty_when_no_skills_saved` | List skills empty when no skills saved. |
| `test_list_skills_reports_a_recorded_skill_with_demo_profit` | List skills reports a recorded skill with demo profit. |
| `test_list_skills_reports_a_mined_skill_with_miner_stats` | List skills reports a mined skill with miner stats. |
| `test_list_skills_includes_drafts_only_when_asked` | List skills includes drafts only when asked. |
| `test_list_skills_carries_live_progress_for_the_currently_armed_loop` | List skills carries live progress for the currently armed loop. |
| `test_play_start_arms_the_loop_and_status_reports_progress` | Play start arms the loop and status reports progress. |
| `test_play_start_missing_name_is_rejected` | Play start missing name is rejected. |
| `test_play_start_unknown_skill_is_rejected` | Play start unknown skill is rejected. |
| `test_play_start_refuses_while_human_attached` | Play start refuses while human attached. |
| `test_play_stop_always_allowed_even_mid_run` | Play stop always allowed even mid run. |
| `test_play_stop_with_nothing_running_is_a_harmless_no_op` | Play stop with nothing running is a harmless no op. |
| `test_play_pause_and_resume_round_trip` | Play pause and resume round trip. |
| `test_play_pause_with_nothing_running_is_rejected` | Play pause with nothing running is rejected. |
| `test_replay_and_play_verbs_are_rejected_during_an_active_attach` | Replay and play verbs are rejected during an active attach. |
| `test_do_is_rejected_with_a_distinct_error_while_auto_loop_is_running` | Do is rejected with a distinct error while auto loop is running. |
| `test_do_response_carries_sent_input_and_cursor` | Do response carries sent input and cursor. |
| `test_do_response_redacts_sent_input_for_a_secret_send` | Do response redacts sent input for a secret send. |
| `test_screen_response_carries_the_most_recently_sent_input` | Screen response carries the most recently sent input. |
| `test_status_autopilot_trace_is_none_when_no_engine_is_wired` | Status autopilot trace is none when no engine is wired. |
| `test_status_autopilot_field_matches_loop_snapshot_when_armed` | WO-STATUS-AUTOLOOP-FIELD: status.autopilot mirrors AutopilotLoop.snapshot keys. |
| `test_status_autopilot_trace_surfaces_the_engines_most_recent_dry_run_tick` | Status autopilot trace surfaces the engines most recent dry run tick. |
| `test_status_intervention_clear_when_autopilot_running` | Healthy autopilot: needs_attention false; freshness unknowns may still appear. |
| `test_status_intervention_needs_attention_on_autopilot_sticky_halt` | Sticky halt: last_error set while loop not running raises needs_attention. |
| `test_status_intervention_needs_attention_on_no_candidates_stop` | WO-INTERVENTION-AP-HALT-ATTENTION: quiet no_candidates stop is attention. |
| `test_status_intervention_needs_attention_on_max_ticks_exhausted` | WO-INTERVENTION-AP-HALT-ATTENTION: tick-cap exit raises attention. |
| `test_status_intervention_needs_attention_on_game_select_halt` | WO-AP-GAME-SELECT-RECOVER: stop_reason=game_select → attention code. |
| `test_status_intervention_needs_attention_on_explore_exhausted` | WO-INTERVENTION-EXPLORE-EXHAUSTED-CODE: dedicated reason + sticky halt. |
| `test_status_intervention_running_no_candidates_is_not_attention` | Still-running AP with last_reason=no_candidates stays healthy (continuous). |
| `test_status_intervention_needs_attention_when_human_attached` | Status intervention needs attention when human attached. |
| `test_status_intervention_credits_stale_is_informational_not_attention` | Stale credits flag reason without needs_attention when autopilot healthy. |
| `test_status_seeds_fighters_aboard_from_info_screen` | WO-FIGHTERS-STATUS-FRESH: Info/`I` viewport stamps fighters; omits fighters_unknown. |
