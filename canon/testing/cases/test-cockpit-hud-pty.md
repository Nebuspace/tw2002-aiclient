---
type: Reference
title: Test Cases — test_cockpit_hud_pty
description: WO-P3-037 wire -- HUD freshness markers, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_hud_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_hud_pty.py`

_WO-P3-037 wire -- HUD freshness markers, Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_hud_labels_visible_in_order` | Full tier hud labels visible in order. |
| `test_narrow_tier_hud_labels_visible_in_order` | Narrow tier hud labels visible in order. |
| `test_no_provider_hud_shows_honest_all_dash_cold_state` | No provider hud shows honest all dash cold state. |
| `test_full_tier_fresh_fixture_shows_value_and_freshness_stamp` | Full tier fresh fixture shows value and freshness stamp. |
| `test_full_tier_stale_fixture_value_still_renders` | Full tier stale fixture value still renders. |
| `test_full_tier_cjk_credits_value_preserves_hud_right_border` | CREDITS' value is 40 CJK/fullwidth glyphs (2 cells each) -- 80 cells against the HUD box's ~34-cell interior. |
| `test_full_tier_escape_sequence_value_neutralized_not_interpreted` | Full tier escape sequence value neutralized not interpreted. |
| `test_hud_stale_value_rows_dim_label_rows_stay_normal` | Hud stale value rows dim label rows stay normal. |
| `test_poll_guard_one_call_at_minimal_tier_with_control_strip_as_sole_consumer` | Poll guard one call at minimal tier with control strip as sole consumer. |
| `test_poll_guard_fires_when_hud_is_sole_surviving_status_consumer` | PWO-037 guard-extension regression. |
| `test_hud_composer_and_wire_have_no_ai_pilot_badge_or_send_surface` | Hud composer and wire have no ai pilot badge or send surface. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | Play shell screen handle key unchanged esc and q only. |
