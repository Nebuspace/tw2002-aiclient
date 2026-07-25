---
type: Reference
title: Test Cases — test_cockpit_focus_pty
description: WO-P3-035 wire — FOCUS panel retitle + live compose, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_focus_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_focus_pty.py`

_WO-P3-035 wire — FOCUS panel retitle + live compose, Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_goals_and_focus_titles_visible` | Full tier goals and focus titles visible. |
| `test_narrow_right_gutter_tier_goals_and_focus_titles_visible` | Narrow right gutter tier goals and focus titles visible. |
| `test_no_provider_focus_shows_honest_empty` | No provider focus shows honest empty. |
| `test_full_tier_stubbed_provider_shows_ranked_and_gated_lines` | Full tier stubbed provider shows ranked and gated lines. |
| `test_narrow_tier_stubbed_provider_shows_ranked_and_gated_lines` | Narrow tier stubbed provider shows ranked and gated lines. |
| `test_focus_composer_source_has_no_send_or_socket_surface` | Grep-level static check (PREP hard-gate): the FOCUS composer is display-only -- it must never contain a send/socket-write call. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | Play shell screen handle key unchanged esc and q only. |
