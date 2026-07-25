---
type: Reference
title: Test Cases — test_watchfeed
description: Watchfeed.
resource: repo://tw2002-aiclient/tests/test_watchfeed.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_watchfeed.py`

_Watchfeed._

| Test | Blurb |
|------|-------|
| `test_settle_events_recorded_latest_wins` | Settle events recorded latest wins. |
| `test_subscribe_line_is_the_only_write_ever` | Hostile write-capture assert: the ONE subscribe line, and nothing else -- across repeated snapshot() calls and repeated stop() calls. |
| `test_malformed_line_dropped_mid_stream` | Malformed line dropped mid stream. |
| `test_eof_ends_stream_gracefully` | Eof ends stream gracefully. |
| `test_stop_idempotent_before_and_mid_stream` | Stop idempotent before and mid stream. |
| `test_start_with_raising_connect_fn_is_contained` | Start with raising connect fn is contained. |
| `test_start_with_write_failure_after_connect_is_contained` | Start with write failure after connect is contained. |
| `test_stop_during_blocked_connect_closes_fresh_transport_no_send` | Stop during blocked connect closes fresh transport no send. |
| `test_default_connect_fn_failure_is_contained` | Default connect fn failure is contained. |
| `test_snapshot_thread_safety_smoke` | Snapshot thread safety smoke. |
