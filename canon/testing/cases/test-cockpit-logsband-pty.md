---
type: Reference
title: Test Cases — Cockpit Logsband Pty
description: WO-P3-041 wire -- LOGS band advancing transcript tail + newest-row flash,.
resource: repo://tw2002-aiclient/tests/test_cockpit_logsband_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_logsband_pty.py`

_WO-P3-041 wire -- LOGS band advancing transcript tail + newest-row flash,_

| Test | Blurb |
|------|-------|
| `test_logs_title_and_real_tail_line_visible_and_not_flashing` | Logs title and real tail line visible and not flashing. |
| `test_advancing_tail_shows_a_strictly_later_number_after_more_ticks` | Advancing tail shows a strictly later number after more ticks. |
| `test_newest_row_stays_bold_while_the_tail_keeps_advancing` | Newest row stays bold while the tail keeps advancing. |
| `test_secret_marker_present_and_sentinel_absent_from_logs_band` | Secret marker present and sentinel absent from logs band. |
| `test_no_log_tail_field_falls_back_to_status_line` | No log tail field falls back to status line. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | Play shell screen handle key unchanged esc and q only. |
| `test_embedded_newline_in_tail_line_does_not_escape_box` | Embedded newline in tail line does not escape box. |
| `test_poll_guard_still_fires_exactly_once_with_logs_consuming_the_snapshot` | Poll guard still fires exactly once with logs consuming the snapshot. |
| `test_status_line_fallback_used_when_no_real_tail` | Status line fallback used when no real tail. |
| `test_real_tail_supersedes_status_line_fallback` | Real tail supersedes status line fallback. |
| `test_flash_state_persists_across_unchanged_newest_then_resets_on_change` | Flash state persists across unchanged newest then resets on change. |
| `test_flash_state_resets_when_tail_reverts_to_honest_empty` | Flash state resets when tail reverts to honest empty. |
| `test_raising_now_fn_does_not_crash_draw_and_logs_still_renders` | Mirrors tests/test_cockpit_liveness_pty. |
| `test_raising_status_provider_falls_back_to_honest_state` | Raising status provider falls back to honest state. |
