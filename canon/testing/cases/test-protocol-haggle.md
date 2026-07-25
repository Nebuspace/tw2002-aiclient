---
type: Reference
title: Test Cases — Protocol Haggle
description: protocol.
resource: repo://tw2002-aiclient/tests/test_protocol_haggle.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_protocol_haggle.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_protocol.py's `haggle` verb dispatch -- no network, a scripted fake_

| Test | Blurb |
|------|-------|
| `test_haggle_verb_runs_the_negotiation_and_reports_the_outcome` | Haggle verb runs the negotiation and reports the outcome. |
| `test_haggle_verb_no_active_haggle_still_returns_ok_with_the_current_screen` | Haggle verb no active haggle still returns ok with the current screen. |
| `test_haggle_verb_honors_explicit_strategy_overrides_from_args` | Haggle verb honors explicit strategy overrides from args. |
| `test_haggle_verb_records_exactly_one_ledger_entry_when_a_ledger_is_wired` | Haggle verb records exactly one ledger entry when a ledger is wired. |
| `test_haggle_verb_ledgers_the_freshness_gated_screen_not_the_transitional_one` | Haggle verb ledgers the freshness gated screen not the transitional one. |
| `test_haggle_verb_records_actor_trainer_not_the_mode_derived_ai_default` | Haggle verb records actor trainer not the mode derived ai default. |
