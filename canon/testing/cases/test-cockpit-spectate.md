---
type: Reference
title: Test Cases — Cockpit Spectate
description: PWO-055 -- product spectate state, Layer-A + a cheap fake-window wiring.
resource: repo://tw2002-aiclient/tests/test_cockpit_spectate.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_spectate.py`

_PWO-055 -- product spectate state, Layer-A + a cheap fake-window wiring_

| Test | Blurb |
|------|-------|
| `test_seat_label_is_the_canon_cited_word` | Seat label is the canon cited word. |
| `test_seat_label_true_renders_the_label` | Seat label true renders the label. |
| `test_seat_label_false_yields_empty` | Seat label false yields empty. |
| `test_seat_label_any_truthy_value_renders_the_label` | Seat label any truthy value renders the label. |
| `test_seat_label_any_falsy_value_yields_empty` | Seat label any falsy value yields empty. |
| `test_seat_label_unevaluable_input_degrades_to_the_calm_spectate_reading` | Seat label unevaluable input degrades to the calm spectate reading. |
| `test_combines_label_left_and_liveness_right_with_full_width_result` | Combines label left and liveness right with full width result. |
| `test_not_spectating_renders_liveness_only_right_justified` | Not spectating renders liveness only right justified. |
| `test_matches_prior_behavior_when_not_spectating_and_width_positive` | Matches prior behavior when not spectating and width positive. |
| `test_zero_or_negative_width_yields_empty_string` | Zero or negative width yields empty string. |
| `test_non_finite_width_never_raises` | Non finite width never raises. |
| `test_hostile_liveness_text_type_degrades_to_empty_liveness_not_a_crash` | Hostile liveness text type degrades to empty liveness not a crash. |
| `test_label_drops_when_no_room_for_a_separator_column` | Label drops when no room for a separator column. |
| `test_label_drops_when_gap_is_exactly_one_column` | Label drops when gap is exactly one column. |
| `test_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column` | Label truncates to fit a narrow gap leaving a separator column. |
| `test_empty_liveness_text_and_spectating_still_fits_label_alone` | Empty liveness text and spectating still fits label alone. |
| `test_unicode_ok_flag_has_no_effect_ascii_only_label` | Unicode ok flag has no effect ascii only label. |
| `test_never_raises_on_wildly_hostile_arguments` | Never raises on wildly hostile arguments. |
| `test_entry_default_renders_app_chip_matching_the_daemons_own_mode` | RENAMED + RE-JUSTIFIED (prior name: ``test_default_spectating_true_. |
| `test_entry_default_mirrors_a_freshly_constructed_control_locks_own_mode` | The other half of the citation above, executed rather than quoted:. |
| `test_returning_from_spectate_to_app_hold_renders_app_not_liveness_only` | RENAMED TWICE, and the reason matters both times. |
| `test_toggling_spectating_false_and_attached_true_renders_manual` | The genuine "switch to Human" wiring proof WO-P5-060's own screens. |
| `test_control_strip_row_attr_is_muted_a_normal` | Canon: Spectate is "muted / plain" -- achieved here for free because. |
| `test_raising_control_seat_composer_does_not_crash_draw_and_liveness_survives` | A raising `compose_control_strip_segments` (WO-P5-060: this is the. |
| `test_minimal_tier_still_renders_the_label_no_side_gutters` | CONTROL_STRIP is present at every reachable non-too_small tier. |
| `test_handle_key_unchanged_no_new_keys_from_this_wo` | PWO-055 adds no keyboard handling of its own (spectate is the. |
| `test_manual_label_is_the_canon_cited_word` | Manual label is the canon cited word. |
| `test_attached_label_true_renders_the_label` | Attached label true renders the label. |
| `test_attached_label_false_yields_empty` | Attached label false yields empty. |
| `test_attached_label_any_truthy_value_renders_the_label` | Attached label any truthy value renders the label. |
| `test_attached_label_any_falsy_value_yields_empty` | Attached label any falsy value yields empty. |
| `test_attached_label_unevaluable_input_degrades_to_no_claim` | Attached label unevaluable input degrades to no claim. |
| `test_compose_control_strip_line_default_attached_is_false_backward_compat` | Compose control strip line default attached is false backward compat. |
| `test_attached_true_renders_manual_label_left_anchored` | Attached true renders manual label left anchored. |
| `test_attached_true_wins_over_spectating_true` | Attached true wins over spectating true. |
| `test_attached_false_and_spectating_false_renders_app_label` | Attached false and spectating false renders app label. |
| `test_manual_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column` | Manual label truncates to fit a narrow gap leaving a separator column. |
| `test_manual_label_drops_when_no_room_for_a_separator_column` | Manual label drops when no room for a separator column. |
| `test_unicode_ok_flag_has_no_effect_on_manual_label_either` | Unicode ok flag has no effect on manual label either. |
| `test_never_raises_with_hostile_attached_argument_too` | Never raises with hostile attached argument too. |
| `test_app_label_is_the_canon_cited_word` | App label is the canon cited word. |
| `test_app_label_function_always_returns_the_label` | App label function always returns the label. |
| `test_app_label_never_the_retired_vocabulary` | App label never the retired vocabulary. |
| `test_selection_matrix_spectating_true_attached_false_is_spectate` | Selection matrix spectating true attached false is spectate. |
| `test_selection_matrix_spectating_false_attached_true_is_manual` | Selection matrix spectating false attached true is manual. |
| `test_selection_matrix_spectating_false_attached_false_is_app` | Selection matrix spectating false attached false is app. |
| `test_selection_matrix_both_truthy_attached_wins_not_app_not_spectate` | Selection matrix both truthy attached wins not app not spectate. |
| `test_neither_spectating_nor_attached_renders_app_label_left_anchored` | Neither spectating nor attached renders app label left anchored. |
| `test_segments_app_chip_carries_ok_tone` | Segments app chip carries ok tone. |
| `test_segments_manual_chip_carries_warn_tone` | Segments manual chip carries warn tone. |
| `test_segments_spectate_chip_carries_no_tone_stays_plain` | Segments spectate chip carries no tone stays plain. |
| `test_segments_default_arguments_are_spectating_true_attached_false` | Segments default arguments are spectating true attached false. |
| `test_segments_invalid_width_returns_empty_list` | Segments invalid width returns empty list. |
| `test_segments_unicode_ok_flag_has_no_effect` | Segments unicode ok flag has no effect. |
| `test_segments_never_raises_on_wildly_hostile_arguments` | Segments never raises on wildly hostile arguments. |
| `test_segments_concatenation_matches_compose_control_strip_line` | Segments concatenation matches compose control strip line. |
| `test_app_label_drops_when_no_room_for_a_separator_column` | App label drops when no room for a separator column. |
| `test_app_label_drops_when_gap_is_exactly_one_column` | App label drops when gap is exactly one column. |
| `test_app_label_truncates_to_fit_a_narrow_gap_leaving_a_separator_column` | App label truncates to fit a narrow gap leaving a separator column. |
| `test_app_label_renders_in_full_with_a_generous_gap` | App label renders in full with a generous gap. |
| `test_app_label_empty_liveness_text_still_fits_label_alone` | App label empty liveness text still fits label alone. |
| `test_degrade_matrix_label_matches_priority_oracle_and_never_raises` | Degrade matrix label matches priority oracle and never raises. |
| `test_app_renders_iff_literal_false_on_both_axes_self_contained` | The PRIMARY pin for the App-eligibility gate -- deliberately. |
| `test_degrade_direction_never_invents_app_from_unknown_or_garbage_state` | Degrade direction never invents app from unknown or garbage state. |
| `test_both_none_never_renders_app_or_any_other_claim` | Both none never renders app or any other claim. |
| `test_falsy_but_non_bool_spectating_never_clears_the_app_bar` | Falsy but non bool spectating never clears the app bar. |
| `test_raising_attached_with_definitively_false_spectating_never_renders_app` | Raising attached with definitively false spectating never renders app. |
| `test_degrade_matrix_never_raises_at_narrow_and_zero_widths_too` | Degrade matrix never raises at narrow and zero widths too. |
| `test_no_retired_vocabulary_anywhere_in_module_constants` | No retired vocabulary anywhere in module constants. |
