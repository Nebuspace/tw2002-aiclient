---
type: Reference
title: Test Cases — test_guardian
description: SessionGuardian tests (WO-P2-027 reconnect+replay; WO-P2-028 keepalive).
resource: repo://tw2002-aiclient/tests/test_guardian.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_guardian.py`

_SessionGuardian tests (WO-P2-027 reconnect+replay; WO-P2-028 keepalive)._

| Test | Blurb |
|------|-------|
| `test_keepalive_fires_on_idle_main_command` | Keepalive fires on idle main command. |
| `test_keepalive_does_not_fire_below_idle_threshold` | Keepalive does not fire below idle threshold. |
| `test_keepalive_never_fires_on_password_screen_even_if_idle` | Keepalive never fires on password screen even if idle. |
| `test_keepalive_never_fires_on_port_trade_screen_even_if_idle` | Keepalive never fires on port trade screen even if idle. |
| `test_keepalive_never_fires_on_unknown_screen_even_if_idle` | Keepalive never fires on unknown screen even if idle. |
| `test_keepalive_never_fires_on_confirm_screen_even_if_idle` | Keepalive never fires on confirm screen even if idle. |
| `test_keepalive_never_fires_on_combat_class_even_if_idle` | Keepalive never fires on combat class even if idle. |
| `test_keepalive_at_most_one_per_idle_window` | Keepalive at most one per idle window. |
| `test_keepalive_skipped_when_disconnected` | Keepalive skipped when disconnected. |
| `test_keepalive_skipped_during_reconnect_burst` | Keepalive skipped during reconnect burst. |
| `test_reconnect_skipped_without_a_recorded_profile` | Reconnect skipped without a recorded profile. |
| `test_reconnect_replays_saved_password_login_to_main_command` | Reconnect replays saved password login to main command. |
| `test_reconnect_retries_after_a_failed_attempt_then_succeeds` | Reconnect retries after a failed attempt then succeeds. |
| `test_reconnect_gives_up_after_max_attempts_without_raising` | Reconnect gives up after max attempts without raising. |
| `test_reconnect_without_saved_password_surfaces_as_last_error_not_a_crash` | Reconnect without saved password surfaces as last error not a crash. |
| `test_reconnect_unverified_screen_is_not_reported_as_success` | Resume success iff verified main_command — unknown/stuck ≠ success. |
