---
type: Reference
title: Test Cases — Cockpit Decisions Pty
description: WO-P3-036 wire — DECISIONS panel stacked below HUD, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_decisions_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_decisions_pty.py`

_WO-P3-036 wire — DECISIONS panel stacked below HUD, Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_hud_and_decisions_titles_visible` | Full tier hud and decisions titles visible. |
| `test_narrow_right_gutter_tier_hud_and_decisions_titles_visible` | Narrow right gutter tier hud and decisions titles visible. |
| `test_no_provider_decisions_shows_honest_empty` | No provider decisions shows honest empty. |
| `test_full_tier_stubbed_provider_shows_chosen_and_gated_lines` | Full tier stubbed provider shows chosen and gated lines. |
| `test_narrow_tier_stubbed_provider_shows_chosen_and_gated_lines` | Narrow tier stubbed provider shows chosen and gated lines. |
| `test_decisions_composer_and_wire_have_no_ai_pilot_badge_or_send_surface` | D5 (PREP hard-gate): no ``ai_pilot``/``AI-PILOT`` badge text anywhere. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | DECISIONS wiring must not add any new key handling -- Esc still. |
