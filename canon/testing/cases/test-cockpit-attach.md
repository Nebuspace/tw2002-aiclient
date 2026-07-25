---
type: Reference
title: Test Cases — test_cockpit_attach
description: WO-P4-056 lane A -- Ctrl-A attaches the cockpit to the daemon's Human control lock (canon `mode-line-and-teach-controls.md:40-47`).
resource: repo://tw2002-aiclient/tests/test_cockpit_attach.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_attach.py`

_WO-P4-056 lane A -- Ctrl-A attaches the cockpit to the daemon's Human control lock (canon `mode-line-and-teach-controls.md:40-47`)._

| Test | Blurb |
|------|-------|
| `test_handle_key_ctrl_a_signals_attach_intent` | WO-P5-061-ENTRY: Ctrl-A (ASCII 1) is the RULED Mode chord. |
| `test_handle_key_m_and_shift_m_no_longer_signal_attach_intent` | WO-P5-061-ENTRY corollary: no single printable key may ever be Mode -- `M`/`m` must NOT return `"attach"` anymore. |
| `test_handle_key_unrelated_keys_unaffected_by_ctrl_a_addition` | Handle key unrelated keys unaffected by ctrl a addition. |
| `test_attempt_attach_take_held_conflict_path` | Attempt attach take held conflict path. |
| `test_attempt_attach_daemon_not_running_is_handled_honestly` | Attempt attach daemon not running is handled honestly. |
| `test_run_play_ctrl_a_attaches_forwards_a_keystroke_and_esc_releases` | WO-P5-061-ENTRY: Ctrl-A, not `M`, is the attach trigger. |
| `test_run_play_forwards_q_shift_q_and_bare_m_while_attached_esc_and_ctrl_a_reserved` | Run play forwards q shift q and bare m while attached esc and ctrl a reserved. |
| `test_run_play_forwards_backspace_in_every_raw_form_as_canonical_bs` | Hub ruling (WO-P4-056 REVISE): backspace forwarding is mandatory, not a disclosed gap -- a human who can't correct a typo while attached is materially impaired. |
| `test_run_play_attach_refusal_is_honest_not_silent_success` | Run play attach refusal is honest not silent success. |
| `test_run_play_broken_attach_connection_falls_back_to_spectate_honestly` | Run play broken attach connection falls back to spectate honestly. |
| `test_control_strip_transitions_app_spectate_manual_and_back` | Addendum pin (Samantha): the TRANSITION, not just an end state -- WO-P4-054 taught us a one-way assertion can't prove a state surface actually returns. |
| `test_detach_key_flips_spectating_true_and_signals_detach_and_releases_lock` | Detach key flips spectating true and signals detach and releases lock. |
| `test_detach_then_fresh_attach_succeeds_proving_lock_released` | Detach then fresh attach succeeds proving lock released. |
| `test_no_send_after_detach_and_keys_route_through_handle_key_again` | No send after detach and keys route through handle key again. |
| `test_double_detach_is_a_safe_no_op` | Double detach is a safe no op. |
| `test_detach_after_broken_wire_fallback_is_also_a_safe_no_op` | Detach after broken wire fallback is also a safe no op. |
| `test_esc_is_not_detach_still_ends_the_binding_via_finally_release` | Esc is not detach still ends the binding via finally release. |
| `test_control_strip_chip_restores_to_spectate_after_detach` | Control strip chip restores to spectate after detach. |
| `test_watchfeed_survives_detach_still_running_and_provider_still_bound` | Watchfeed survives detach still running and provider still bound. |
| `test_app_hold_daemon_seat_truth_default_mode_is_app_not_a_client_fiction` | App hold daemon seat truth default mode is app not a client fiction. |
| `test_app_hold_ctrl_a_attaches_to_human_lock_and_manual_chip_renders` | App hold ctrl a attaches to human lock and manual chip renders. |
| `test_ctrl_bracket_from_app_hold_is_a_no_op_state_unchanged_deliberately_ruled` | Accept #4 (WO-P5-061): Ctrl-] FROM App-hold is a DELIBERATE no-op -- owner ruling, 2026-07-25 ("Ctrl-] from App-hold = a deliberate no-op. |
| `test_ctrl_a_from_human_releases_to_app_hold_not_spectate` | Ctrl a from human releases to app hold not spectate. |
| `test_ctrl_a_release_then_fresh_attach_succeeds_proving_lock_released` | Ctrl a release then fresh attach succeeds proving lock released. |
| `test_ctrl_a_release_no_further_send_and_keys_route_through_handle_key_again` | Ctrl a release no further send and keys route through handle key again. |
| `test_app_hold_chip_renders_after_ctrl_a_release_from_human` | App hold chip renders after ctrl a release from human. |
