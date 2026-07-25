---
type: Reference
title: Test Cases — test_clean_preempt
description: Clean preempt.
resource: repo://tw2002-aiclient/tests/test_clean_preempt.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_clean_preempt.py`

_Clean preempt._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_do_verb_flags_interrupted_by_human_when_fenced_mid_flight` | Do verb flags interrupted by human when fenced mid flight. |
| `test_do_verb_leaves_interrupted_by_human_false_when_never_fenced_sensitivity_control` | Do verb leaves interrupted by human false when never fenced sensitivity control. |
| `test_do_verb_explicit_actor_human_for_spectate_idle_overlay` | Do verb explicit actor human for spectate idle overlay. |
| `test_send_verb_also_flags_interrupted_by_human_when_fenced_mid_flight` | Send verb also flags interrupted by human when fenced mid flight. |
| `test_record_attach_keystroke_writes_actor_human_row_via_real_ledger` | Record attach keystroke writes actor human row via real ledger. |
| `test_record_attach_keystroke_is_a_no_op_when_server_has_no_ledger` | Record attach keystroke is a no op when server has no ledger. |
| `test_record_attach_keystroke_redacts_when_told_secret_is_true` | Record attach keystroke redacts when told secret is true. |
| `test_dispatch_replay_wires_is_driver_fenced_through_to_replay_skill` | Dispatch replay wires is driver fenced through to replay skill. |
| `test_dispatch_play_wires_is_driver_fenced_through_to_play_skill` | Dispatch play wires is driver fenced through to play skill. |
| `test_dispatch_crawl_start_wires_is_driver_fenced_through_to_run_live_crawl` | Dispatch crawl start wires is driver fenced through to run live crawl. |
| `test_record_attach_keystroke_does_not_redact_when_told_secret_is_false` | Record attach keystroke does not redact when told secret is false. |
