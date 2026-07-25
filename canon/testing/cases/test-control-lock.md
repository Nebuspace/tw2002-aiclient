---
type: Reference
title: Test Cases — Control Lock
description: ControlLock (tw2002_aiclient.
resource: repo://tw2002-aiclient/tests/test_control_lock.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_control_lock.py`

_ControlLock (tw2002_aiclient.session.control_lock) — pure unit tests._

| Test | Blurb |
|------|-------|
| `test_app_may_send_by_default` | App may send by default. |
| `test_exposed_modes_are_exactly_app_human_spectate` | Exposed modes are exactly app human spectate. |
| `test_take_human_blocks_app` | Take human blocks app. |
| `test_take_human_twice_raises` | Take human twice raises. |
| `test_release_human_returns_to_app` | Release human returns to app. |
| `test_release_human_is_safe_when_not_held` | Release human is safe when not held. |
| `test_take_human_again_after_release_succeeds` | Take human again after release succeeds. |
| `test_set_mode_switches_between_settable_modes` | Set mode switches between settable modes. |
| `test_set_mode_rejects_unknown_mode_name` | Set mode rejects unknown mode name. |
| `test_set_mode_rejects_auto_loop_alias` | Set mode rejects auto loop alias. |
| `test_set_mode_cannot_enter_human_mode` | Set mode cannot enter human mode. |
| `test_set_mode_cannot_clobber_an_active_human_attach` | Set mode cannot clobber an active human attach. |
| `test_set_mode_cannot_clobber_a_running_auto_loop` | Set mode cannot clobber a running auto loop. |
| `test_enter_auto_loop_collapses_to_app` | Enter auto loop collapses to app. |
| `test_enter_auto_loop_twice_raises` | Enter auto loop twice raises. |
| `test_enter_auto_loop_refuses_to_preempt_an_active_attach` | Enter auto loop refuses to preempt an active attach. |
| `test_take_human_always_wins_over_auto_loop` | Take human always wins over auto loop. |
| `test_leave_auto_loop_clears_hold_keeps_app` | Leave auto loop clears hold keeps app. |
| `test_leave_auto_loop_is_safe_when_not_held` | Leave auto loop is safe when not held. |
| `test_enter_auto_loop_again_after_leave_succeeds` | Enter auto loop again after leave succeeds. |
| `test_is_driving_false_by_default` | Is driving false by default. |
| `test_acquire_driver_marks_is_driving_true` | Acquire driver marks is driving true. |
| `test_acquire_driver_twice_raises_controller_busy` | Acquire driver twice raises controller busy. |
| `test_release_driver_clears_is_driving` | Release driver clears is driving. |
| `test_release_driver_is_safe_when_not_held` | Release driver is safe when not held. |
| `test_acquire_driver_again_after_release_succeeds` | Acquire driver again after release succeeds. |
| `test_enter_auto_loop_refuses_to_preempt_an_active_driver` | Enter auto loop refuses to preempt an active driver. |
| `test_acquire_driver_refuses_when_auto_loop_holds` | Acquire driver refuses when auto loop holds. |
| `test_acquire_driver_refuses_when_human_attach_holds` | Acquire driver refuses when human attach holds. |
| `test_acquire_driver_refuses_in_spectate` | Acquire driver refuses in spectate. |
| `test_take_human_never_refuses_while_driving` | Take human never refuses while driving. |
| `test_is_driver_fenced_false_by_default` | Is driver fenced false by default. |
| `test_take_human_does_not_fence_when_nothing_is_driving` | Take human does not fence when nothing is driving. |
| `test_release_driver_clears_the_fence` | Release driver clears the fence. |
| `test_fresh_acquire_driver_after_a_fenced_release_starts_unfenced` | Fresh acquire driver after a fenced release starts unfenced. |
| `test_driver_lock_never_leaks_after_a_dispatch_ends` | Driver lock never leaks after a dispatch ends. |
| `test_no_legacy_drive_mode_symbols_exported` | No legacy drive mode symbols exported. |
