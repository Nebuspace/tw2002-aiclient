---
type: Reference
title: Test Cases — Watch
description: WatchHub settle-edge detection + subscriber fan-out — no network, no.
resource: repo://tw2002-aiclient/tests/test_watch.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_watch.py`

_WatchHub settle-edge detection + subscriber fan-out — no network, no_

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
| `test_loop_tick_exception_text_never_leaks_into_last_loop_error` | WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 3 (Cipher rule): only the. |
| `test_broadcast_exception_text_never_leaks_into_error_or_event` | Same Cipher pin as above, at the ``_broadcast()`` containment. |
| `test_stop_returns_promptly_even_with_a_long_poll_interval` | WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 4. |
| `test_status_reports_subscriber_count` | Status reports subscriber count. |
