---
type: Reference
title: Test Cases — test_cockpit_mode_badge
description: WO-P5-060 lane B -- App/Human control-strip mode-badge wiring.
resource: repo://tw2002-aiclient/tests/test_cockpit_mode_badge.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_mode_badge.py`

_WO-P5-060 lane B -- App/Human control-strip mode-badge wiring._

| Test | Blurb |
|------|-------|
| `test_two_segments_paint_left_to_right_with_own_attrs` | Two segments paint left to right with own attrs. |
| `test_segment_straddling_budget_truncates_and_starves_the_next_segment` | Segment straddling budget truncates and starves the next segment. |
| `test_wide_char_straddling_the_boundary_drops_whole_not_split` | Wide char straddling the boundary drops whole not split. |
| `test_wide_char_that_fits_exactly_renders_in_full` | Wide char that fits exactly renders in full. |
| `test_control_char_sanitized_to_space_across_segment_boundary` | Control char sanitized to space across segment boundary. |
| `test_cross_segment_clip_matches_single_string_equivalent` | Cross segment clip matches single string equivalent. |
| `test_malformed_segments_are_dropped_survivors_still_render` | Malformed segments are dropped survivors still render. |
| `test_none_region_is_a_silent_noop` | None region is a silent noop. |
| `test_empty_segments_is_a_silent_noop` | Empty segments is a silent noop. |
| `test_unboxed_region_uses_raw_bounds_no_inset` | Unboxed region uses raw bounds no inset. |
| `test_zero_width_budget_renders_nothing` | Zero width budget renders nothing. |
| `test_wiring_matrix_chip_text_and_attr_per_state` | Wiring matrix chip text and attr per state. |
| `test_color_path_combines_allocated_pair_with_bold_reverse` | Color path combines allocated pair with bold reverse. |
| `test_xor_at_the_wire_exactly_one_chip_ever_renders` | Xor at the wire exactly one chip ever renders. |
| `test_app_hold_to_manual_walk_app_chip_before_manual_after_never_both` | App hold to manual walk app chip before manual after never both. |
