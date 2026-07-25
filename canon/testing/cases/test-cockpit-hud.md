---
type: Reference
title: Test Cases — Cockpit Hud
description: Pure HUD-panel composer tests (PWO-037, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_hud.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_hud.py`

_Pure HUD-panel composer tests (PWO-037, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_freshness_zero_is_now` | Freshness zero is now. |
| `test_freshness_just_under_one_second_is_now` | Freshness just under one second is now. |
| `test_freshness_exactly_one_second_is_ns_ago` | Freshness exactly one second is ns ago. |
| `test_freshness_truncates_fractional_seconds` | Freshness truncates fractional seconds. |
| `test_freshness_no_minutes_tier_keeps_counting_seconds` | Freshness no minutes tier keeps counting seconds. |
| `test_freshness_ascii_mark_when_unicode_disabled` | Freshness ascii mark when unicode disabled. |
| `test_freshness_ascii_now_when_unicode_disabled` | Freshness ascii now when unicode disabled. |
| `test_freshness_negative_age_clamps_to_now` | Freshness negative age clamps to now. |
| `test_freshness_never_raises_on_hostile_direct_input` | Freshness never raises on hostile direct input. |
| `test_freshness_raising_float_dunder_never_raises` | Freshness raising float dunder never raises. |
| `test_status_none_all_ten_lines_unknown` | Status none all ten lines unknown. |
| `test_status_empty_dict_matches_none` | Status empty dict matches none. |
| `test_status_missing_hud_key_matches_none` | Status missing hud key matches none. |
| `test_non_dict_status_never_raises_and_matches_none` | Non dict status never raises and matches none. |
| `test_non_dict_hud_payload_never_raises_and_matches_none` | Non dict hud payload never raises and matches none. |
| `test_field_order_and_labels_fixed_regardless_of_hud_key_order` | Field order and labels fixed regardless of hud key order. |
| `test_ten_lines_always_regardless_of_width` | Ten lines always regardless of width. |
| `test_full_fixture_exact_lines` | Full fixture exact lines. |
| `test_positive_profit_gets_explicit_plus_sign` | Positive profit gets explicit plus sign. |
| `test_sector_and_cargo_render_without_thousands_separator` | Sector and cargo render without thousands separator. |
| `test_credits_and_turns_render_with_thousands_separator` | Credits and turns render with thousands separator. |
| `test_stale_boundary_just_under_threshold_not_stale` | Stale boundary just under threshold not stale. |
| `test_stale_boundary_exactly_at_threshold_is_stale` | Stale boundary exactly at threshold is stale. |
| `test_stale_boundary_well_past_threshold_is_stale` | Stale boundary well past threshold is stale. |
| `test_label_rows_never_stale_even_when_value_row_is` | Label rows never stale even when value row is. |
| `test_missing_field_is_unknown` | Missing field is unknown. |
| `test_value_none_is_unknown_regardless_of_age` | Value none is unknown regardless of age. |
| `test_field_slot_not_a_dict_is_unknown` | Field slot not a dict is unknown. |
| `test_age_none_renders_value_with_no_stamp_not_stale` | Age none renders value with no stamp not stale. |
| `test_age_missing_key_renders_value_with_no_stamp` | Age missing key renders value with no stamp. |
| `test_negative_age_clamps_to_zero_and_reads_now` | Negative age clamps to zero and reads now. |
| `test_bool_value_renders_as_true_false_text_not_numeric` | Bool value renders as true false text not numeric. |
| `test_str_value_renders_verbatim_never_reformatted_as_number` | Str value renders verbatim never reformatted as number. |
| `test_str_value_is_trimmed` | Str value is trimmed. |
| `test_whole_valued_float_formats_without_trailing_point_zero` | Whole valued float formats without trailing point zero. |
| `test_non_integer_float_value_still_renders` | Non integer float value still renders. |
| `test_non_finite_value_never_raises_and_degrades_to_unknown` | Non finite value never raises and degrades to unknown. |
| `test_non_finite_or_unparsable_age_never_raises_and_omits_stamp` | Non finite or unparsable age never raises and omits stamp. |
| `test_raising_str_dunder_on_value_degrades_to_unknown` | Raising str dunder on value degrades to unknown. |
| `test_raising_float_dunder_on_age_never_raises` | Raising float dunder on age never raises. |
| `test_hostile_int_like_value_object_falls_back_to_str` | Hostile int like value object falls back to str. |
| `test_dict_subclass_field_slot_with_hostile_get_is_contained` | Dict subclass field slot with hostile get is contained. |
| `test_huge_int_credits_never_raises_and_formats` | Huge int credits never raises and formats. |
| `test_ascii_mark_swap_applies_to_every_stamped_value` | Ascii mark swap applies to every stamped value. |
| `test_unicode_mark_is_default` | Unicode mark is default. |
| `test_width_clip_sweep_every_line_within_budget` | Width clip sweep every line within budget. |
| `test_width_zero_or_negative_empties_every_line` | Width zero or negative empties every line. |
| `test_width_zero_preserves_stale_flags` | Width zero preserves stale flags. |
| `test_width_non_int_never_raises_and_empties` | Width non int never raises and empties. |
| `test_width_none_never_raises_and_empties` | Width none never raises and empties. |
| `test_width_non_finite_float_never_raises_and_empties` | Width non finite float never raises and empties. |
| `test_narrow_width_clips_mid_value` | Narrow width clips mid value. |
