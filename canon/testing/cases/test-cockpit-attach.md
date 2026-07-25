---
type: Reference
title: Test Cases — Cockpit Attach
description: WO-P4-056 lane A -- Ctrl-A attaches the cockpit to the daemon's Human.
resource: repo://tw2002-aiclient/tests/test_cockpit_attach.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_attach.py`

_WO-P4-056 lane A -- Ctrl-A attaches the cockpit to the daemon's Human_

| Test | Blurb |
|------|-------|
| `test_handle_key_ctrl_a_signals_attach_intent` | WO-P5-061-ENTRY: Ctrl-A (ASCII 1) is the RULED Mode chord. |
| `test_handle_key_m_and_shift_m_no_longer_signal_attach_intent` | WO-P5-061-ENTRY corollary: no single printable key may ever be. |
| `test_handle_key_unrelated_keys_unaffected_by_ctrl_a_addition` | Handle key unrelated keys unaffected by ctrl a addition. |
| `test_attempt_attach_take_held_conflict_path` | Attempt attach take held conflict path. |
| `test_attempt_attach_daemon_not_running_is_handled_honestly` | Attempt attach daemon not running is handled honestly. |
| `test_run_play_ctrl_a_attaches_forwards_a_keystroke_and_esc_releases` | WO-P5-061-ENTRY: Ctrl-A, not `M`, is the attach trigger. |
| `test_run_play_forwards_q_shift_q_and_bare_m_while_attached_esc_and_ctrl_a_reserved` | Regression pin (Samantha REVISE, WO-P4-056), EXTENDED by WO-P5-061-. |
| `test_run_play_forwards_backspace_in_every_raw_form_as_canonical_bs` | Hub ruling (WO-P4-056 REVISE): backspace forwarding is mandatory,. |
| `test_run_play_attach_refusal_is_honest_not_silent_success` | Run play attach refusal is honest not silent success. |
| `test_run_play_broken_attach_connection_falls_back_to_spectate_honestly` | A mid-session forward failure (broken pipe, daemon gone, . |
| `test_control_strip_transitions_app_spectate_manual_and_back` | Addendum pin (Samantha): the TRANSITION, not just an end state --. |
| `test_detach_key_flips_spectating_true_and_signals_detach_and_releases_lock` | Detach key flips spectating true and signals detach and releases lock. |
| `test_detach_then_fresh_attach_succeeds_proving_lock_released` | Detach then fresh attach succeeds proving lock released. |
| `test_no_send_after_detach_and_keys_route_through_handle_key_again` | No send after detach and keys route through handle key again. |
| `test_double_detach_is_a_safe_no_op` | Double detach is a safe no op. |
| `test_detach_after_broken_wire_fallback_is_also_a_safe_no_op` | Proof 4 addendum: a Ctrl-] pressed AFTER an already-broken attach. |
| `test_esc_is_not_detach_still_ends_the_binding_via_finally_release` | Regression pin: Esc (27) stays the pre-existing, DIFFERENT exit --. |
| `test_control_strip_chip_restores_to_spectate_after_detach` | Control strip chip restores to spectate after detach. |
| `test_watchfeed_survives_detach_still_running_and_provider_still_bound` | Watchfeed survives detach still running and provider still bound. |
| `test_app_hold_daemon_seat_truth_default_mode_is_app_not_a_client_fiction` | Kernel item 1: control_lock. |
| `test_app_hold_ctrl_a_attaches_to_human_lock_and_manual_chip_renders` | Accept #1 (WO-P5-061): from App-hold (driven directly here, exactly. |
| `test_ctrl_bracket_from_app_hold_is_a_no_op_state_unchanged_deliberately_ruled` | Accept #4 (WO-P5-061): Ctrl-] FROM App-hold is a DELIBERATE no-op --. |
| `test_ctrl_a_from_human_releases_to_app_hold_not_spectate` | Accept #2 (WO-P5-061-ENTRY): Ctrl-A while attached hands the seat to. |
| `test_ctrl_a_release_then_fresh_attach_succeeds_proving_lock_released` | Mirrors `test_detach_then_fresh_attach_succeeds_proving_lock_. |
| `test_ctrl_a_release_no_further_send_and_keys_route_through_handle_key_again` | Mirrors `test_no_send_after_detach_and_keys_route_through_handle_. |
| `test_app_hold_chip_renders_after_ctrl_a_release_from_human` | The paint-side counterpart: once Ctrl-A hands the seat back to. |
