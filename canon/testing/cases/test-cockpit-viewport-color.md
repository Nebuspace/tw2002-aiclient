---
type: Reference
title: Test Cases — Cockpit Viewport Color
description: Tests for the pure pyte-color-run -> curses-attr mapping (WO-P4-053.
resource: repo://tw2002-aiclient/tests/test_cockpit_viewport_color.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_viewport_color.py`

_Tests for the pure pyte-color-run -> curses-attr mapping (WO-P4-053_

| Test | Blurb |
|------|-------|
| `test_pyte_to_curses_color_covers_exactly_the_real_pyte_names` | Pyte to curses color covers exactly the real pyte names. |
| `test_curses_color_of_maps_every_real_pyte_name` | Curses color of maps every real pyte name. |
| `test_curses_color_of_default_and_unknown_and_hostile_are_minus_one` | Curses color of default and unknown and hostile are minus one. |
| `test_exact_run_survives_unchanged_when_fully_in_bounds` | Exact run survives unchanged when fully in bounds. |
| `test_output_length_always_matches_text_lines_length` | Output length always matches text lines length. |
| `test_row_count_matches_color_rows_with_no_transform_needed` | Row count matches color rows with no transform needed. |
| `test_top_drop_alignment_bottom_anchors_surviving_color_rows` | Top drop alignment bottom anchors surviving color rows. |
| `test_fewer_color_rows_than_text_lines_pads_leading_rows_uncolored` | Fewer color rows than text lines pads leading rows uncolored. |
| `test_run_straddling_the_clipped_width_boundary_truncates_not_drops` | Run straddling the clipped width boundary truncates not drops. |
| `test_run_entirely_beyond_the_clipped_width_is_dropped` | Run entirely beyond the clipped width is dropped. |
| `test_run_spanning_the_whole_original_row_clips_to_new_row_length` | Run spanning the whole original row clips to new row length. |
| `test_negative_start_clamps_to_zero_rather_than_dropping` | Negative start clamps to zero rather than dropping. |
| `test_text_lines_not_a_list_or_tuple_is_empty` | Text lines not a list or tuple is empty. |
| `test_empty_text_lines_is_empty` | Empty text lines is empty. |
| `test_color_rows_row_not_a_list_degrades_only_that_row` | Color rows row not a list degrades only that row. |
| `test_text_line_not_a_str_treats_row_as_zero_length` | Text line not a str treats row as zero length. |
| `test_malformed_run_shapes_drop_without_raising` | Malformed run shapes drop without raising. |
| `test_one_malformed_run_does_not_drop_sibling_valid_runs_in_the_same_row` | One malformed run does not drop sibling valid runs in the same row. |
| `test_run_attr_calls_attr_for_with_the_runs_fg_and_bg` | Run attr calls attr for with the runs fg and bg. |
| `test_run_attr_ors_bold_only_when_true` | Run attr ors bold only when true. |
| `test_run_attr_hostile_bold_value_is_never_treated_as_true` | Run attr hostile bold value is never treated as true. |
| `test_run_attr_non_dict_run_is_normal_and_never_calls_attr_for` | Run attr non dict run is normal and never calls attr for. |
| `test_run_attr_missing_fg_bg_still_calls_attr_for_with_none_no_crash` | Run attr missing fg bg still calls attr for with none no crash. |
