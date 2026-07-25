---
type: Reference
title: Test Cases — test_tw04_toctou
description: TW-04 TOCTOU / refuse-not-queue probes (WO-P2-025).
resource: repo://tw2002-aiclient/tests/test_tw04_toctou.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_tw04_toctou.py`

_TW-04 TOCTOU / refuse-not-queue probes (WO-P2-025)._

| Test | Blurb |
|------|-------|
| `test_real_acquire_driver_blocks_concurrent_take_human_for_the_full_hold` | Real acquire driver blocks concurrent take human for the full hold. |
| `test_real_enter_auto_loop_blocks_concurrent_acquire_driver_for_the_full_hold` | Real enter auto loop blocks concurrent acquire driver for the full hold. |
| `test_naive_two_step_acquire_driver_lets_take_human_interleave_mid_gap` | Naive two step acquire driver lets take human interleave mid gap. |
| `test_acquire_driver_refuses_not_queues_when_busy` | Acquire driver refuses not queues when busy. |
| `test_acquire_driver_refuses_not_queues_when_human_holds` | Acquire driver refuses not queues when human holds. |
| `test_take_human_fences_in_flight_driver_without_refusing` | Take human fences in flight driver without refusing. |
| `test_send_raw_waits_for_fenced_driver_then_sends` | Send raw waits for fenced driver then sends. |
