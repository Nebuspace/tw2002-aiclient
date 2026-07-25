---
type: Reference
title: Test Cases — test_cockpit_draw_runs
description: Cockpit draw runs.
resource: repo://tw2002-aiclient/tests/test_cockpit_draw_runs.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_draw_runs.py`

_Cockpit draw runs._

| Test | Blurb |
|------|-------|
| `test_two_runs_paint_at_exact_offsets_with_own_attrs` | Two runs paint at exact offsets with own attrs. |
| `test_single_run_shorter_than_line_leaves_rest_only_on_base_layer` | Single run shorter than line leaves rest only on base layer. |
| `test_no_runs_only_draws_base_layer` | No runs only draws base layer. |
| `test_runs_none_only_draws_base_layer` | Runs none only draws base layer. |
| `test_run_straddling_right_edge_clips_cleanly` | Run straddling right edge clips cleanly. |
| `test_run_entirely_past_right_edge_produces_no_overlay_write` | Run entirely past right edge produces no overlay write. |
| `test_run_starting_negative_clips_to_left_edge` | Run starting negative clips to left edge. |
| `test_run_exactly_bounding_wide_char_includes_it_whole` | Run exactly bounding wide char includes it whole. |
| `test_run_splitting_wide_char_mid_glyph_drops_it_rather_than_slicing` | Run splitting wide char mid glyph drops it rather than slicing. |
| `test_run_starting_mid_wide_char_skips_it_and_keeps_trailing_char` | Run starting mid wide char skips it and keeps trailing char. |
| `test_non_dict_run_entries_are_dropped_without_crashing` | Non dict run entries are dropped without crashing. |
| `test_run_missing_start_or_end_is_dropped` | Run missing start or end is dropped. |
| `test_run_missing_attr_defaults_to_zero_and_still_paints` | Run missing attr defaults to zero and still paints. |
| `test_empty_span_run_is_dropped` | Empty span run is dropped. |
| `test_inverted_span_run_is_dropped` | Inverted span run is dropped. |
| `test_non_finite_numeric_run_fields_are_dropped_without_crashing` | Non finite numeric run fields are dropped without crashing. |
| `test_runs_field_itself_hostile_non_iterable_falls_back_to_base_layer` | Runs field itself hostile non iterable falls back to base layer. |
| `test_malformed_line_item_shape_is_skipped_entirely` | Malformed line item shape is skipped entirely. |
| `test_non_str_text_line_is_skipped_without_crashing` | Non str text line is skipped without crashing. |
| `test_control_character_inside_a_run_span_is_neutralized` | Control character inside a run span is neutralized. |
| `test_control_character_in_base_layer_is_also_neutralized` | Control character in base layer is also neutralized. |
| `test_boxed_false_uses_full_region_no_inset` | Boxed false uses full region no inset. |
| `test_lines_beyond_interior_height_are_dropped` | Lines beyond interior height are dropped. |
| `test_region_none_is_a_no_op` | Region none is a no op. |
| `test_empty_lines_is_a_no_op` | Empty lines is a no op. |
| `test_multiple_lines_land_at_incrementing_rows` | Multiple lines land at incrementing rows. |
