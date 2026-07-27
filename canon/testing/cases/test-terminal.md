---
type: Reference
title: Test Cases — test_terminal
description: pyte render + crop correctness tests — no network involved.
resource: repo://tw2002-aiclient/tests/test_terminal.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_terminal.py`

_pyte render + crop correctness tests — no network involved._

| Test | Blurb |
|------|-------|
| `test_raw_display_is_80x25` | Raw display is 80x25. |
| `test_empty_screen_crops_to_nothing` | Empty screen crops to nothing. |
| `test_crop_trims_trailing_blank_rows_and_columns` | Crop trims trailing blank rows and columns. |
| `test_crop_keeps_leading_blank_rows` | Crop keeps leading blank rows. |
| `test_crop_width_is_max_content_width_across_rows` | Crop width is max content width across rows. |
| `test_cursor_reports_position` | Cursor reports position. |
| `test_cp437_box_drawing_bytes_decode_to_unicode` | Cp437 box drawing bytes decode to unicode. |
| `test_ansi_color_sequences_still_work_alongside_cp437_bytes` | Ansi color sequences still work alongside cp437 bytes. |
| `test_color_map_empty_screen` | Color map empty screen. |
| `test_color_map_single_run_for_uncolored_text` | Color map single run for uncolored text. |
| `test_color_map_splits_runs_at_attribute_changes` | Color map splits runs at attribute changes. |
| `test_color_map_captures_bold_and_background` | Color map captures bold and background. |
| `test_color_map_aligned_with_render_cropped_bounding_box` | Color map aligned with render cropped bounding box. |
