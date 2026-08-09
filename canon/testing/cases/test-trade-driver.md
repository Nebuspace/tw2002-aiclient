---
type: Reference
title: Test Cases — test_trade_driver
description: tests/test_trade_driver.py -- WO-FA4 trade_driver.py: the money-path chain-execution driver.
resource: repo://tw2002-aiclient/tests/test_trade_driver.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_trade_driver.py`

_tests/test_trade_driver.py -- WO-FA4 trade_driver.py: the money-path chain-execution driver._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_run_chain_completes_a_scripted_two_port_loop_with_exact_credits_math` | Run chain completes a scripted two port loop with exact credits math. |
| `test_realized_losing_hop_aborts_before_the_next_buy` | FA3 ranks on an explicitly unverified pct curve; FA4 must treat live transaction totals as authoritative. |
| `test_should_abort_true_at_hop_entry_produces_zero_sends` | The whole-chain tick's kill switch must be able to abort BEFORE the very first send if it's already true at hop entry. |
| `test_should_abort_mid_chain_halts_at_the_next_send_step_not_chain_end` | Should abort mid chain halts at the next send step not chain end. |
| `test_is_armed_false_produces_zero_sends_fail_closed` | Is armed false produces zero sends fail closed. |
| `test_sell_side_genuine_zero_bracket_holds_cargo_stranded_never_completes` | Sell side genuine zero bracket holds cargo stranded never completes. |
| `test_dock_turn_floor_gates_the_actual_sell_dock_not_just_the_upfront_estimate` | Dock turn floor gates the actual sell dock not just the upfront estimate. |
| `test_low_turns_holds_before_the_stranding_hop` | Low turns holds before the stranding hop. |
| `test_credit_delta_anomaly_fires_on_a_magnitude_mismatch_even_with_correct_direction` | Credit delta anomaly fires on a magnitude mismatch even with correct direction. |
| `test_buy_quantity_is_computed_from_budget_never_the_ports_own_max_default` | Buy quantity is computed from budget never the ports own max default. |
| `test_over_budget_offer_holds_without_ever_accepting` | A live total that comes back over (credits - cash_floor) must HOLD -- never accept, never counter (bounded-HOLD backstop). |
| `test_depleted_stock_stops_the_chain_cleanly` | Depleted stock stops the chain cleanly. |
| `test_unexpected_screen_holds_instead_of_retry_spinning` | A screen that matches NONE of the recognized shapes must HOLD immediately -- never spin retrying the same send. |
| `test_paladin_send_letter_refuses_any_letter_outside_the_allowlist` | Paladin send letter refuses any letter outside the allowlist. |
| `test_on_progress_fires_at_each_hop_boundary_and_once_more_at_chain_end` | On progress fires at each hop boundary and once more at chain end. |
| `test_on_progress_callback_exception_is_swallowed_never_aborts_the_chain` | On progress callback exception is swallowed never aborts the chain. |
