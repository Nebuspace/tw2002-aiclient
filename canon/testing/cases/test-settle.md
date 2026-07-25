---
type: Reference
title: Test Cases — Settle
description: Settle-detection timing tests with a fake clock — no real sleeping.
resource: repo://tw2002-aiclient/tests/test_settle.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_settle.py`

_Settle-detection timing tests with a fake clock — no real sleeping._

| Test | Blurb |
|------|-------|
| `test_no_bytes_at_all_hits_timeout` | No bytes at all hits timeout. |
| `test_idle_settle_after_debounce_following_a_byte` | Idle settle after debounce following a byte. |
| `test_never_settles_idle_without_any_new_bytes` | Idle can only fire once >=1 byte has arrived since the send —. |
| `test_prompt_match_wins_immediately_even_before_any_sleep` | Prompt match wins immediately even before any sleep. |
| `test_wait_prompt_case_mismatch_times_out_never_matches` | Canon invariant: wait_prompt is case-sensitive (no IGNORECASE). |
| `test_prompt_match_arriving_later_beats_idle_and_timeout` | Prompt match arriving later beats idle and timeout. |
| `test_timeout_fires_even_with_traffic_if_no_prompt_and_never_idle` | Timeout fires even with traffic if no prompt and never idle. |
| `test_wait_until_settled_reports_idle_immediately_if_already_quiet_before_the_call` | Wait until settled reports idle immediately if already quiet before the call. |
| `test_wait_until_settled_keeps_waiting_while_new_bytes_keep_arriving` | Wait until settled keeps waiting while new bytes keep arriving. |
| `test_wait_until_settled_times_out_if_traffic_never_goes_quiet` | Wait until settled times out if traffic never goes quiet. |
| `test_wait_until_settled_never_reports_idle_with_zero_bytes_ever_received` | Wait until settled never reports idle with zero bytes ever received. |
| `test_send_and_confirm_happy_path_matches_and_stays_stable` | Send and confirm happy path matches and stays stable. |
| `test_send_and_confirm_passes_enter_false_and_secret_through_to_send` | Send and confirm passes enter false and secret through to send. |
| `test_send_and_confirm_rejects_a_transient_flicker_not_yet_settled` | Send and confirm rejects a transient flicker not yet settled. |
| `test_send_and_confirm_true_when_prompt_stays_stable_past_the_recheck` | Send and confirm true when prompt stays stable past the recheck. |
| `test_send_and_confirm_never_matching_is_a_safe_desync_not_a_guess` | Send and confirm never matching is a safe desync not a guess. |
| `test_send_and_confirm_none_confirms_via_a_stable_idle_settle` | Send and confirm none confirms via a stable idle settle. |
| `test_send_and_confirm_none_rejects_when_more_bytes_arrive_during_the_recheck` | Send and confirm none rejects when more bytes arrive during the recheck. |
| `test_send_and_confirm_retry_unstable_idle_confirms_after_late_paint` | WO-SETTLE-EARLY: live 3034→250 / 4571→2429 class — first idle. |
| `test_send_and_confirm_retry_unstable_idle_still_times_out_when_never_quiet` | WO-SETTLE-EARLY Accept: bounded wait — continuous traffic never. |
| `test_send_and_confirm_loops_past_a_premature_idle_to_find_the_real_match` | Send and confirm loops past a premature idle to find the real match. |
| `test_send_and_confirm_prompt_given_still_times_out_when_never_matched` | Send and confirm prompt given still times out when never matched. |
| `test_send_and_confirm_rejects_a_stale_confirm_prompt_match_predating_this_send` | Send and confirm rejects a stale confirm prompt match predating this send. |
| `test_send_and_confirm_never_confirms_on_pre_send_content_with_nothing_new_arriving` | Send and confirm never confirms on pre send content with nothing new arriving. |
| `test_send_and_confirm_none_mode_never_idle_confirms_with_zero_bytes_since_send` | Send and confirm none mode never idle confirms with zero bytes since send. |
