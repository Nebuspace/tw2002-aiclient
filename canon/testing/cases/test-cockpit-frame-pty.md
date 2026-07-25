---
type: Reference
title: Test Cases — Cockpit Frame Pty
description: WO-P3-030-033 — Trainer-cockpit frame chrome (PWO-031/033), Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_frame_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_frame_pty.py`

_WO-P3-030-033 — Trainer-cockpit frame chrome (PWO-031/033), Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_outer_frame_double_line_corners_cyan_bold` | Full tier outer frame double line corners cyan bold. |
| `test_full_tier_panel_titles_at_expected_rows` | Full tier panel titles at expected rows. |
| `test_full_tier_strip_shows_host_and_handle_on_row_1` | Full tier strip shows host and handle on row 1. |
| `test_full_tier_strip_row_is_data_not_chrome_colored` | Pixel canon ruling: strip content is profile identity DATA, never. |
| `test_full_tier_center_viewport_is_double_line_and_empty_panels_honest` | PWO-051: the GAME viewport's own honesty is a BLANK grid -- no. |
| `test_ascii_twin_closure_glyphs_no_unicode_leak` | Ascii twin closure glyphs no unicode leak. |
| `test_narrow_run_left_gutter_absent_frame_flush_to_right_edge` | Narrow run left gutter absent frame flush to right edge. |
| `test_cjk_heavy_status_line_preserves_logs_right_border` | Cjk heavy status line preserves logs right border. |
| `test_embedded_newline_in_status_line_does_not_escape_box` | Embedded newline in status line does not escape box. |
| `test_tall_terminal_leaves_reserved_band_unpainted` | Tall terminal leaves reserved band unpainted. |
| `test_too_small_refuses_with_message_and_no_chrome` | Too small refuses with message and no chrome. |
| `test_draw_box_overlong_title_does_not_clobber_top_right_corner` | A title far longer than the box's own interior must not bleed past. |
| `test_draw_lines_attrs_applies_a_distinct_attr_per_line` | draw_lines_attrs's whole reason to exist: two lines in the SAME box. |
| `test_draw_lines_attrs_clips_wide_glyphs_to_interior_cell_width` | A CJK/fullwidth line (2 cells per glyph) must clip by DISPLAY WIDTH,. |
| `test_draw_lines_attrs_sanitizes_embedded_control_char` | An embedded control character (\n) must be neutralized to a plain. |
