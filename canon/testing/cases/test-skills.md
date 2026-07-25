---
type: Reference
title: Test Cases — test_skills
description: Skill record/replay + playback tests (DESIGN-v2 §3 v2.1 item 11b/11d, C3) -- no network.
resource: repo://tw2002-aiclient/tests/test_skills.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_skills.py`

_Skill record/replay + playback tests (DESIGN-v2 §3 v2.1 item 11b/11d, C3) -- no network._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_skill_recorder_not_recording_by_default` | Skill recorder not recording by default. |
| `test_skill_recorder_start_stop_round_trip` | Skill recorder start stop round trip. |
| `test_skill_recorder_start_while_recording_raises` | Skill recorder start while recording raises. |
| `test_skill_recorder_auto_generates_name_when_omitted` | Skill recorder auto generates name when omitted. |
| `test_record_step_no_op_when_not_recording` | Record step no op when not recording. |
| `test_skill_recorder_persists_start_anchor_from_start_call` | Skill recorder persists start anchor from start call. |
| `test_skill_recorder_start_anchor_defaults_to_none_when_omitted` | Skill recorder start anchor defaults to none when omitted. |
| `test_save_skill_persists_start_anchor` | Save skill persists start anchor. |
| `test_save_skill_start_anchor_defaults_to_none` | Save skill start anchor defaults to none. |
| `test_save_and_load_skill_round_trip` | Save and load skill round trip. |
| `test_load_missing_skill_raises` | Load missing skill raises. |
| `test_load_skill_with_valid_json_but_no_steps_raises_clean_skill_error` | Load skill with valid json but no steps raises clean skill error. |
| `test_load_skill_rejects_a_json_document_that_is_not_an_object` | Load skill rejects a json document that is not an object. |
| `test_skill_name_sanitized_for_path_traversal` | Skill name sanitized for path traversal. |
| `test_draft_and_real_skills_live_in_separate_dirs` | Draft and real skills live in separate dirs. |
| `test_record_then_replay_round_trip` | Record then replay round trip. |
| `test_replay_skill_succeeds_when_every_step_matches_expected` | Replay skill succeeds when every step matches expected. |
| `test_replay_skill_halts_on_post_class_divergence` | Replay skill halts on post class divergence. |
| `test_replay_skill_halts_on_unmodeled_screen_even_without_expected` | Replay skill halts on unmodeled screen even without expected. |
| `test_replay_skill_applies_params_via_format_substitution` | Replay skill applies params via format substitution. |
| `test_replay_skill_falls_back_to_literal_when_no_matching_param` | Replay skill falls back to literal when no matching param. |
| `test_play_skill_runs_requested_cycles_and_reports_cycles_complete` | Play skill runs requested cycles and reports cycles complete. |
| `test_play_skill_halts_on_surprise_mid_run` | Play skill halts on surprise mid run. |
| `test_play_skill_halts_on_floor_stop_loss` | Play skill halts on floor stop loss. |
| `test_play_skill_halts_credits_unknown_when_no_balance_was_ever_observed` | Play skill halts credits unknown when no balance was ever observed. |
| `test_play_skill_halts_credits_unknown_on_a_session_without_the_supervision_surface` | Play skill halts credits unknown on a session without the supervision surface. |
| `test_play_skill_halts_credits_unknown_on_a_stale_balance` | Play skill halts credits unknown on a stale balance. |
| `test_play_skill_credits_stale_ms_is_config_driven_not_hardcoded` | Play skill credits stale ms is config driven not hardcoded. |
| `test_play_skill_proceeds_on_a_fresh_confirmed_balance_strictly_above_floor` | The proceed path: a fresh, confirmed balance strictly greater than `floor` must NOT halt -- the run completes its cycles normally. |
| `test_play_skill_price_mask_below_floor_poc_reads_the_strict_balance_not_the_loose_price_quote` | Play skill price mask below floor poc reads the strict balance not the loose price quote. |
| `test_play_skill_rejects_cycles_over_the_hard_cap` | Play skill rejects cycles over the hard cap. |
| `test_replay_skill_refuses_when_current_sector_mismatches_start_anchor` | Replay skill refuses when current sector mismatches start anchor. |
| `test_replay_skill_refuses_when_current_sector_cannot_be_determined` | Replay skill refuses when current sector cannot be determined. |
| `test_replay_skill_proceeds_when_current_sector_matches_start_anchor` | Replay skill proceeds when current sector matches start anchor. |
| `test_replay_skill_refuses_unanchored_skill_by_default` | Replay skill refuses unanchored skill by default. |
| `test_replay_skill_force_bypasses_a_missing_start_anchor` | Replay skill force bypasses a missing start anchor. |
| `test_replay_skill_force_does_not_bypass_a_detected_mismatch` | Replay skill force does not bypass a detected mismatch. |
| `test_play_skill_halts_on_start_anchor_mismatch_mid_run` | Play skill halts on start anchor mismatch mid run. |
| `test_replay_skill_writes_one_ledger_row_per_step_with_trainer_actor` | Replay skill writes one ledger row per step with trainer actor. |
| `test_replay_skill_records_a_ledger_row_even_for_the_diverging_step` | Replay skill records a ledger row even for the diverging step. |
| `test_replay_skill_ledger_stays_a_no_op_when_not_provided` | Replay skill ledger stays a no op when not provided. |
| `test_play_skill_forwards_ledger_and_session_id_across_every_cycle` | Play skill forwards ledger and session id across every cycle. |
| `test_replay_skill_stops_firing_further_sends_once_fenced_mid_run` | Replay skill stops firing further sends once fenced mid run. |
| `test_replay_skill_completes_every_step_when_never_fenced_sensitivity_control` | Replay skill completes every step when never fenced sensitivity control. |
| `test_replay_skill_is_a_no_op_wait_when_is_driver_fenced_not_provided` | Replay skill is a no op wait when is driver fenced not provided. |
| `test_play_skill_halts_with_human_fenced_when_the_driver_is_fenced_mid_cycle` | Play skill halts with human fenced when the driver is fenced mid cycle. |
| `test_replay_skill_mid_animation_screen_change_halts_cleanly_not_a_misfire` | Replay skill mid animation screen change halts cleanly not a misfire. |
| `test_replay_skill_slow_hub_warp_does_not_false_halt_on_premature_idle` | Replay skill slow hub warp does not false halt on premature idle. |
| `test_play_skill_treats_a_confirm_failure_as_a_surprise_halt` | Play skill treats a confirm failure as a surprise halt. |
| `test_replay_skill_end_to_end_never_auto_fires_the_colonist_takeover_default` | Replay skill end to end never auto fires the colonist takeover default. |
