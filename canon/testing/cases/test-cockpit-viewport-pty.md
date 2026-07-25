---
type: Reference
title: Test Cases — Cockpit Viewport Pty
description: WO-P4-051, lane B -- GAME viewport shell, real-curses pty proof.
resource: repo://tw2002-aiclient/tests/test_cockpit_viewport_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_viewport_pty.py`

_WO-P4-051, lane B -- GAME viewport shell, real-curses pty proof._

| Test | Blurb |
|------|-------|
| `test_full_tier_placeholder_absent_from_entire_grid` | Full tier placeholder absent from entire grid. |
| `test_full_tier_game_title_on_center_top_border_row` | Full tier game title on center top border row. |
| `test_full_tier_center_interior_blank_across_full_80_col_width` | Full tier center interior blank across full 80 col width. |
| `test_full_tier_center_double_border_corners_present` | Full tier center double border corners present. |
| `test_minimal_tier_bordered_viewport_present_and_sane` | Minimal tier bordered viewport present and sane. |
| `test_minimal_tier_placeholder_absent` | Minimal tier placeholder absent. |
| `test_no_border_tier_draws_without_crash_placeholder_absent` | No border tier draws without crash placeholder absent. |
| `test_no_border_tier_center_region_has_no_stray_text` | No border tier center region has no stray text. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | Play shell screen handle key unchanged esc and q only. |
| `test_ascii_twin_full_tier_game_box_ascii_corners_no_unicode_leak` | Ascii twin full tier game box ascii corners no unicode leak. |
