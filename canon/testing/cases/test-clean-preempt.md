---
type: Reference
title: Test Cases — Clean Preempt
description: WO-CLEANPREEMPT: control_lock.
resource: repo://tw2002-aiclient/tests/test_clean_preempt.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_clean_preempt.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_WO-CLEANPREEMPT: control_lock.ControlLock.take_human() fences an_

| Test | Blurb |
|------|-------|
| `test_do_verb_flags_interrupted_by_human_when_fenced_mid_flight` | Do verb flags interrupted by human when fenced mid flight. |
| `test_do_verb_leaves_interrupted_by_human_false_when_never_fenced_sensitivity_control` | Sensitivity control for the test above: identical shape, but. |
| `test_do_verb_explicit_actor_human_for_spectate_idle_overlay` | Spectate idle-prompt overlay passes actor=human so autonomy. |
| `test_send_verb_also_flags_interrupted_by_human_when_fenced_mid_flight` | The `send` verb shares `_record_ledger`'s same `interrupted_by_. |
| `test_record_attach_keystroke_writes_actor_human_row_via_real_ledger` | Record attach keystroke writes actor human row via real ledger. |
| `test_record_attach_keystroke_is_a_no_op_when_server_has_no_ledger` | Record attach keystroke is a no op when server has no ledger. |
| `test_record_attach_keystroke_redacts_when_told_secret_is_true` | WO-CLEANPREEMPT (secret sub-diff): `secret` is now a REQUIRED. |
| `test_dispatch_replay_wires_is_driver_fenced_through_to_replay_skill` | Dispatch replay wires is driver fenced through to replay skill. |
| `test_dispatch_play_wires_is_driver_fenced_through_to_play_skill` | Dispatch play wires is driver fenced through to play skill. |
| `test_dispatch_crawl_start_wires_is_driver_fenced_through_to_run_live_crawl` | Dispatch crawl start wires is driver fenced through to run live crawl. |
| `test_record_attach_keystroke_does_not_redact_when_told_secret_is_false` | Sensitivity control for the redaction test above: `secret=False`. |
