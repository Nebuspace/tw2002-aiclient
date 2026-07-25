---
type: Reference
title: Test Cases — Watchfeed
description: Layer-A tests for ``tw2002_aiclient.
resource: repo://tw2002-aiclient/tests/test_watchfeed.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_watchfeed.py`

_Layer-A tests for ``tw2002_aiclient.watchfeed.WatchFeed`` (WO-P4-050,_

| Test | Blurb |
|------|-------|
| `test_settle_events_recorded_latest_wins` | Settle events recorded latest wins. |
| `test_subscribe_line_is_the_only_write_ever` | Hostile write-capture assert: the ONE subscribe line, and nothing. |
| `test_malformed_line_dropped_mid_stream` | Malformed line dropped mid stream. |
| `test_eof_ends_stream_gracefully` | Eof ends stream gracefully. |
| `test_stop_idempotent_before_and_mid_stream` | Stop idempotent before and mid stream. |
| `test_start_with_raising_connect_fn_is_contained` | Start with raising connect fn is contained. |
| `test_start_with_write_failure_after_connect_is_contained` | Same fd-leak shape as the raced-stop regression below, different. |
| `test_stop_during_blocked_connect_closes_fresh_transport_no_send` | Mack adversarial-review regression (HIGH, WO-P4-050 in-wave fix):. |
| `test_default_connect_fn_failure_is_contained` | Exercises the REAL default daemon-socket connect path (not a test. |
| `test_snapshot_thread_safety_smoke` | Snapshot thread safety smoke. |
