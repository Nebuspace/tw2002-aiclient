---
type: Reference
title: Test Cases — test_actor_attribution
description: Actor attribution at the send choke point (WO-P2-025).
resource: repo://tw2002-aiclient/tests/test_actor_attribution.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_actor_attribution.py`

_Actor attribution at the send choke point (WO-P2-025)._

| Test | Blurb |
|------|-------|
| `test_valid_senders_are_app_and_human_only` | Valid senders are app and human only. |
| `test_send_defaults_to_app_and_records_last_sender` | Send defaults to app and records last sender. |
| `test_send_raw_defaults_to_human_and_records_last_sender` | Send raw defaults to human and records last sender. |
| `test_send_rejects_legacy_ai_sender` | Send rejects legacy ai sender. |
| `test_send_rejects_legacy_trainer_sender` | Send rejects legacy trainer sender. |
| `test_send_raw_rejects_legacy_ai_sender` | Send raw rejects legacy ai sender. |
| `test_explicit_human_sender_on_send_is_recorded` | Explicit human sender on send is recorded. |
| `test_control_lock_default_mode_is_app_not_ai_pilot` | Control lock default mode is app not ai pilot. |
| `test_take_human_flips_mode_to_human_for_attribution_consumers` | Until ledger/_current_actor land, mode + last_sender are the dual attribution surfaces protocol/daemon will read. |
