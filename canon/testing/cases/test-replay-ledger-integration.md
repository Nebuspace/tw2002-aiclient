---
type: Reference
title: Test Cases — Replay Ledger Integration
description: Cross-lane integration proof (P0 safety batch, 2026-07-19 INTEGRATION.
resource: repo://tw2002-aiclient/tests/test_replay_ledger_integration.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_replay_ledger_integration.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Cross-lane integration proof (P0 safety batch, 2026-07-19 INTEGRATION_

| Test | Blurb |
|------|-------|
| `test_replay_verb_writes_a_real_ledger_row_with_actor_trainer_and_session_id` | Replay verb writes a real ledger row with actor trainer and session id. |
| `test_replay_verb_refuses_a_mismatched_start_anchor_before_any_ledger_row` | The TW-03 guard fires BEFORE the first send when the CURRENT. |
| `test_replay_verb_force_waives_a_missing_legacy_start_anchor` | A skill saved before TW-03 existed (`start_anchor: None`) refuses. |
| `test_replay_verb_returns_clean_error_for_a_steps_less_skill_file` | Replay verb returns clean error for a steps less skill file. |
