---
type: Reference
title: Test Cases — test_cli_attach_interactive_send_failure
description: Cli attach interactive send failure.
resource: repo://tw2002-aiclient/tests/test_cli_attach_interactive_send_failure.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cli_attach_interactive_send_failure.py`

_Cli attach interactive send failure._

| Test | Blurb |
|------|-------|
| `test_failed_send_is_reported_and_exits_non_zero` | Both call sites: send_key() -> False ends the session with a visible error and a non-zero rc. |
| `test_failed_send_stops_the_loop_on_the_first_failure` | Three keys are queued but the wire is dead: the loop leaves after the FIRST failure instead of grinding through the rest into a black hole. |
| `test_failure_path_restores_the_terminal_and_closes_the_connection` | Failure path restores the terminal and closes the connection. |
| `test_failure_is_reported_after_the_terminal_is_restored` | Failure is reported after the terminal is restored. |
| `test_successful_sends_still_loop_until_detach_and_exit_zero` | Regression guard for the fix itself: with a live wire every key is forwarded and only Ctrl-] ends the session, still exit 0, still silent. |
| `test_eof_still_exits_zero` | Eof still exits zero. |
| `test_no_send_key_call_discards_its_return_value` | No send key call discards its return value. |
| `test_tripwire_would_catch_the_original_defect` | The guard above only means something if it can go red -- pinned against the exact pre-fix source shape rather than trusted. |
