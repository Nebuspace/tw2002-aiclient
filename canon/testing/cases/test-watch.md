---
type: Reference
title: Test Cases — test_watch
description: Watch.
resource: repo://tw2002-aiclient/tests/test_watch.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_watch.py`

_Watch._

| Test | Blurb |
|------|-------|
| `test_subscribe_seeds_current_screen_immediately` | Subscribe seeds current screen immediately. |
| `test_no_emit_while_still_receiving_bytes` | No emit while still receiving bytes. |
| `test_emits_on_settle_when_screen_changed` | Emits on settle when screen changed. |
| `test_does_not_re_emit_an_unchanged_screen` | Does not re emit an unchanged screen. |
| `test_fan_out_to_multiple_subscribers` | Fan out to multiple subscribers. |
| `test_unsubscribe_stops_further_delivery` | Unsubscribe stops further delivery. |
| `test_subscriber_count_tracks_subscribe_and_unsubscribe` | Subscriber count tracks subscribe and unsubscribe. |
| `test_broadcast_extra_bypasses_settle_edge` | Broadcast extra bypasses settle edge. |
| `test_loop_survives_a_raising_tick` | WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 1. |
| `test_bad_subscriber_does_not_starve_the_rest` | WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 2. |
| `test_loop_tick_exception_text_never_leaks_into_last_loop_error` | Loop tick exception text never leaks into last loop error. |
| `test_broadcast_exception_text_never_leaks_into_error_or_event` | Broadcast exception text never leaks into error or event. |
| `test_stop_returns_promptly_even_with_a_long_poll_interval` | WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 4. |
| `test_status_reports_subscriber_count` | Status reports subscriber count. |
