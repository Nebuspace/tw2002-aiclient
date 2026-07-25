---
type: Reference
title: Test Cases — Trade Driver
description: tests/test_trade_driver.
resource: repo://tw2002-aiclient/tests/test_trade_driver.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_trade_driver.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_tests/test_trade_driver.py -- WO-FA4 trade_driver.py: the money-path_

| Test | Blurb |
|------|-------|
| `test_run_chain_completes_a_scripted_two_port_loop_with_exact_credits_math` | Landmine coverage: auto-haggle-off (every accept is a blank line,. |
| `test_realized_losing_hop_aborts_before_the_next_buy` | FA3 ranks on an explicitly unverified pct curve; FA4 must treat. |
| `test_should_abort_true_at_hop_entry_produces_zero_sends` | The whole-chain tick's kill switch must be able to abort BEFORE. |
| `test_should_abort_mid_chain_halts_at_the_next_send_step_not_chain_end` | A-M1 (the #1 arm-prerequisite): the abort predicate flipping True. |
| `test_is_armed_false_produces_zero_sends_fail_closed` | Is armed false produces zero sends fail closed. |
| `test_sell_side_genuine_zero_bracket_holds_cargo_stranded_never_completes` | A-M2 (CRITICAL, mack's exact repro): buy 45 Fuel Ore @ PortA (900cr),. |
| `test_dock_turn_floor_gates_the_actual_sell_dock_not_just_the_upfront_estimate` | A-M3 (HIGH, mack's exact repro numbers): a hop whose discovery-time. |
| `test_low_turns_holds_before_the_stranding_hop` | The pre-hop upfront turn-floor check must refuse before ANY send. |
| `test_credit_delta_anomaly_fires_on_a_magnitude_mismatch_even_with_correct_direction` | A-C4: the original check only verified the DIRECTION of the drop. |
| `test_buy_quantity_is_computed_from_budget_never_the_ports_own_max_default` | `parse_haggle`'s totals are per-TRANSACTION, not per-unit -- this. |
| `test_over_budget_offer_holds_without_ever_accepting` | A live total that comes back over (credits - cash_floor) must. |
| `test_depleted_stock_stops_the_chain_cleanly` | If the commodity cascade never shows our target commodity at all. |
| `test_unexpected_screen_holds_instead_of_retry_spinning` | A screen that matches NONE of the recognized shapes must HOLD. |
| `test_paladin_send_letter_refuses_any_letter_outside_the_allowlist` | PALADIN: no combat/attack/genesis verb reachable -- `_send_letter`. |
| `test_on_progress_fires_at_each_hop_boundary_and_once_more_at_chain_end` | On progress fires at each hop boundary and once more at chain end. |
| `test_on_progress_callback_exception_is_swallowed_never_aborts_the_chain` | On progress callback exception is swallowed never aborts the chain. |
