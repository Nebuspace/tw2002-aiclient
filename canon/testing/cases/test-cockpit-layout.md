---
type: Reference
title: Test Cases — test_cockpit_layout
description: Trainer-cockpit frame geometry tests (PWO-031/033, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_layout.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_layout.py`

_Trainer-cockpit frame geometry tests (PWO-031/033, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_too_small_below_line_floor` | Too small below line floor. |
| `test_too_small_below_col_floor` | Too small below col floor. |
| `test_too_small_message_uses_the_times_glyph_not_ascii_x` | Too small message uses the times glyph not ascii x. |
| `test_at_col_floor_is_not_too_small` | At col floor is not too small. |
| `test_at_line_floor_is_not_too_small` | At line floor is not too small. |
| `test_full_tier_at_boundary_154` | Full tier at boundary 154. |
| `test_drops_below_full_at_boundary_minus_one` | Drops below full at boundary minus one. |
| `test_left_gutter_narrowed_at_boundary_138` | Left gutter narrowed at boundary 138. |
| `test_left_gutter_absent_below_boundary_138` | Left gutter absent below boundary 138. |
| `test_right_gutter_present_at_boundary_118` | Right gutter present at boundary 118. |
| `test_drops_to_minimal_below_boundary_118` | Drops to minimal below boundary 118. |
| `test_minimal_tier_at_boundary_82` | Minimal tier at boundary 82. |
| `test_drops_to_no_border_below_boundary_82` | Drops to no border below boundary 82. |
| `test_center_width_is_82_at_full_tier` | Center width is 82 at full tier. |
| `test_center_never_exceeds_viewport_width_across_bordered_tiers` | Center never exceeds viewport width across bordered tiers. |
| `test_game_content_budget_is_80x25_at_full_tier_with_ample_height` | Game content budget is 80x25 at full tier with ample height. |
| `test_game_content_budget_matches_across_every_bordered_tier` | Game content budget matches across every bordered tier. |
| `test_no_border_tier_center_dimensions_clip_to_layout_formula` | No border tier center dimensions clip to layout formula. |
| `test_minimal_tier_center_height_clips_to_layout_formula` | Minimal tier center height clips to layout formula. |
| `test_corner_and_edge_coords_at_40x160` | Corner and edge coords at 40x160. |
| `test_goals_present_and_priorities_narrowed_at_right_gutter_tier` | Goals present and priorities narrowed at right gutter tier. |
| `test_goals_absent_when_left_gutter_absent` | Goals absent when left gutter absent. |
| `test_goals_claims_height_before_priorities_when_column_short` | Goals claims height before priorities when column short. |
| `test_goals_at_least_1x1_when_column_is_extremely_short` | Goals at least 1x1 when column is extremely short. |
| `test_goals_and_priorities_together_span_the_full_left_gutter_height` | Goals and priorities together span the full left gutter height. |
| `test_hud_present_and_decisions_present_at_full_tier` | Hud present and decisions present at full tier. |
| `test_hud_present_and_decisions_present_at_narrowed_right_gutter_tier` | Hud present and decisions present at narrowed right gutter tier. |
| `test_decisions_absent_when_right_gutter_absent` | Decisions absent when right gutter absent. |
| `test_hud_claims_height_before_decisions_when_column_short` | Hud claims height before decisions when column short. |
| `test_hud_at_least_1x1_when_column_is_extremely_short` | Hud at least 1x1 when column is extremely short. |
| `test_hud_and_decisions_together_span_the_full_right_gutter_height` | Hud and decisions together span the full right gutter height. |
| `test_control_strip_present_and_below_logs_at_min_lines_floor` | Control strip present and below logs at min lines floor. |
| `test_control_strip_present_at_no_border_tier` | Control strip present at no border tier. |
| `test_control_strip_never_shrinks_logs_below_its_own_floor` | Control strip never shrinks logs below its own floor. |
| `test_control_strip_drops_first_when_column_has_no_slack` | Control strip drops first when column has no slack. |
| `test_control_strip_absent_in_too_small_mode` | Control strip absent in too small mode. |
| `test_regions_never_overlap_across_a_size_sweep` | Regions never overlap across a size sweep. |
| `test_frame_layout_never_raises_across_extreme_sizes` | Frame layout never raises across extreme sizes. |
| `test_pwo039_five_boundary_fold_ladder_sweep` | Pwo039 five boundary fold ladder sweep. |
