---
type: Reference
title: Test Cases — Watchfeed Wire
description: WO-P4-050 (wire lane) — WatchFeed lifecycle wired into the play shell.
resource: repo://tw2002-aiclient/tests/test_watchfeed_wire.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_watchfeed_wire.py`

_WO-P4-050 (wire lane) — WatchFeed lifecycle wired into the play shell._

| Test | Blurb |
|------|-------|
| `test_enter_play_constructs_and_starts_exactly_one_feed` | Enter play constructs and starts exactly one feed. |
| `test_esc_back_stops_feed_exactly_once` | Esc back stops feed exactly once. |
| `test_quit_from_play_stops_feed` | Quit from play stops feed. |
| `test_two_sequential_play_entries_start_and_stop_independent_feeds` | Re-entering the play shell (back, then play again) starts a FRESH. |
| `test_exception_unwind_from_loop_still_stops_feed` | A crashed play loop must still stop the feed (try/finally proof). |
