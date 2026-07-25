---
type: Reference
title: Test Cases — Cockpit Hud Pty
description: WO-P3-037 wire -- HUD freshness markers, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_hud_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_hud_pty.py`

_WO-P3-037 wire -- HUD freshness markers, Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_hud_labels_visible_in_order` | Full tier hud labels visible in order. |
| `test_narrow_tier_hud_labels_visible_in_order` | Narrow tier hud labels visible in order. |
| `test_no_provider_hud_shows_honest_all_dash_cold_state` | No provider hud shows honest all dash cold state. |
| `test_full_tier_fresh_fixture_shows_value_and_freshness_stamp` | Full tier fresh fixture shows value and freshness stamp. |
| `test_full_tier_stale_fixture_value_still_renders` | PROFIT is aged past FRESHNESS_STALE_S (25s >= 20s) in this fixture --. |
| `test_full_tier_cjk_credits_value_preserves_hud_right_border` | CREDITS' value is 40 CJK/fullwidth glyphs (2 cells each) -- 80 cells. |
| `test_full_tier_escape_sequence_value_neutralized_not_interpreted` | CREDITS' value carries a raw ``ESC[2J`` (erase-display) control. |
| `test_hud_stale_value_rows_dim_label_rows_stay_normal` | The exact ``attr`` argument ``PlayShellScreen. |
| `test_poll_guard_one_call_at_minimal_tier_with_control_strip_as_sole_consumer` | Real (not synthetic) tier: 100x25 lands in ``mode == "minimal"``,. |
| `test_poll_guard_fires_when_hud_is_sole_surviving_status_consumer` | PWO-037 guard-extension regression. |
| `test_hud_composer_and_wire_have_no_ai_pilot_badge_or_send_surface` | D5 (PREP hard-gate): no ``ai_pilot``/``AI-PILOT`` badge text anywhere. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | HUD wiring must not add any new key handling -- Esc still returns. |
