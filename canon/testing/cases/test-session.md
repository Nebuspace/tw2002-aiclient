---
type: Reference
title: Test Cases — Session
description: Session unit tests — no network.
resource: repo://tw2002-aiclient/tests/test_session.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_session.py`

_Session unit tests — no network._

| Test | Blurb |
|------|-------|
| `test_game_select_answered_defaults_false` | Game select answered defaults false. |
| `test_session_id_matches_logger` | Session id matches logger. |
| `test_reconnect_resets_game_select_answered_even_if_it_was_set` | Reconnect resets game select answered even if it was set. |
| `test_send_rejects_invalid_sender` | Send rejects invalid sender. |
| `test_send_records_last_sent_and_sender` | Send records last sent and sender. |
| `test_send_secret_redacts_last_sent` | Send secret redacts last sent. |
| `test_send_raw_sends_immediately_when_control_lock_is_none` | Send raw sends immediately when control lock is none. |
| `test_send_raw_sends_immediately_when_the_lock_is_not_fenced` | Send raw sends immediately when the lock is not fenced. |
| `test_send_raw_waits_for_the_fence_to_clear_before_sending` | Send raw waits for the fence to clear before sending. |
| `test_send_raw_fence_wait_is_bounded_and_sends_anyway_once_the_bound_expires` | Send raw fence wait is bounded and sends anyway once the bound expires. |
| `test_send_raw_passes_secret_true_to_send_bytes_at_a_password_prompt` | Send raw passes secret true to send bytes at a password prompt. |
| `test_send_raw_redacts_last_sent_at_a_password_prompt` | Send raw redacts last sent at a password prompt. |
| `test_send_raw_passes_secret_false_at_an_ordinary_prompt` | Send raw passes secret false at an ordinary prompt. |
| `test_send_raw_uses_the_current_screen_at_send_time_not_a_stale_pre_wait_snapshot` | Send raw uses the current screen at send time not a stale pre wait snapshot. |
| `test_valid_senders_are_app_and_human_only` | Valid senders are app and human only. |
| `test_record_history_caps_at_history_cap` | Record history caps at history cap. |
