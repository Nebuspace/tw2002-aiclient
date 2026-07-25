---
type: Reference
title: Test Cases — Cli Attach Interactive Send Failure
description: WO-AUDIT-ATTACH-SEND-KEY-BOOL — ``tw attach``'s INTERACTIVE loop must.
resource: repo://tw2002-aiclient/tests/test_cli_attach_interactive_send_failure.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cli_attach_interactive_send_failure.py`

_WO-AUDIT-ATTACH-SEND-KEY-BOOL — ``tw attach``'s INTERACTIVE loop must_

| Test | Blurb |
|------|-------|
| `test_failed_send_is_reported_and_exits_non_zero` | Both call sites: send_key() -> False ends the session with a visible. |
| `test_failed_send_stops_the_loop_on_the_first_failure` | Three keys are queued but the wire is dead: the loop leaves after the. |
| `test_failure_path_restores_the_terminal_and_closes_the_connection` | The new early exit must not skip either ``finally:``. |
| `test_failure_is_reported_after_the_terminal_is_restored` | Ordering, not just occurrence: the terminal is already restored when. |
| `test_successful_sends_still_loop_until_detach_and_exit_zero` | Regression guard for the fix itself: with a live wire every key is. |
| `test_eof_still_exits_zero` | Pre-existing behavior, preserved: an empty ``read(1)`` (EOF) leaves. |
| `test_no_send_key_call_discards_its_return_value` | Mechanical guard, not prose: a ``send_key(. |
| `test_tripwire_would_catch_the_original_defect` | The guard above only means something if it can go red -- pinned. |
