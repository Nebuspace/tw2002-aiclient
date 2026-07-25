---
type: Reference
title: Test Cases — test_cockpit_tones
description: Pure semantic-tone module tests (WO-P3-040, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_tones.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_tones.py`

_Pure semantic-tone module tests (WO-P3-040, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_table_has_exactly_seven_keys` | Table has exactly seven keys. |
| `test_table_values_pin_canon_fg_and_bold_exactly` | Table values pin canon fg and bold exactly. |
| `test_table_values_are_plain_tuples_of_str_and_bool` | Table values are plain tuples of str and bool. |
| `test_table_is_a_read_only_mapping_proxy_not_a_plain_dict` | Table is a read only mapping proxy not a plain dict. |
| `test_table_assignment_raises_type_error` | Table assignment raises type error. |
| `test_table_item_deletion_raises_type_error` | Table item deletion raises type error. |
| `test_table_pop_raises_attribute_error` | Table pop raises attribute error. |
| `test_disconnected_is_danger_regardless_of_age` | Disconnected is danger regardless of age. |
| `test_connected_with_no_age_is_ok` | Connected with no age is ok. |
| `test_stale_boundary_just_under_threshold_is_ok` | Stale boundary just under threshold is ok. |
| `test_stale_boundary_exactly_at_threshold_is_warn` | Stale boundary exactly at threshold is warn. |
| `test_stale_boundary_well_past_threshold_is_warn` | Stale boundary well past threshold is warn. |
| `test_stale_threshold_value_is_five_seconds` | Stale threshold value is five seconds. |
| `test_negative_age_clamps_to_zero_and_reads_ok` | Negative age clamps to zero and reads ok. |
| `test_none_connected_is_danger` | None connected is danger. |
| `test_raising_bool_dunder_connected_never_raises_and_degrades_to_warn` | Raising bool dunder connected never raises and degrades to warn. |
| `test_truthy_non_bool_connected_behaves_as_connected` | Truthy non bool connected behaves as connected. |
| `test_falsy_non_bool_connected_behaves_as_disconnected` | Falsy non bool connected behaves as disconnected. |
| `test_hostile_age_never_raises_and_counts_as_not_stale` | Hostile age never raises and counts as not stale. |
| `test_gauge_full_is_ok` | Gauge full is ok. |
| `test_gauge_empty_is_danger` | Gauge empty is danger. |
| `test_gauge_ok_boundary_exactly_at_half_is_ok` | Gauge ok boundary exactly at half is ok. |
| `test_gauge_just_under_half_is_warn` | Gauge just under half is warn. |
| `test_gauge_warn_boundary_exactly_at_point_two_is_warn` | Gauge warn boundary exactly at point two is warn. |
| `test_gauge_just_under_point_two_is_danger` | Gauge just under point two is danger. |
| `test_gauge_out_of_range_above_one_clamps_to_ok` | Gauge out of range above one clamps to ok. |
| `test_gauge_out_of_range_below_zero_clamps_to_danger` | Gauge out of range below zero clamps to danger. |
| `test_hostile_fraction_never_raises_and_degrades_to_warn` | Hostile fraction never raises and degrades to warn. |
| `test_infinite_fraction_never_raises_and_degrades_to_warn` | Infinite fraction never raises and degrades to warn. |
| `test_nan_fraction_does_not_silently_fall_through_to_danger` | Nan fraction does not silently fall through to danger. |
| `test_numeric_string_fraction_coerces_and_classifies` | Numeric string fraction coerces and classifies. |
| `test_status_semantic_always_returns_one_of_the_three_tones` | Status semantic always returns one of the three tones. |
| `test_gauge_semantic_always_returns_one_of_the_three_tones` | Gauge semantic always returns one of the three tones. |
| `test_gauge_semantic_never_returns_a_non_finite_or_nan_lookalike` | Gauge semantic never returns a non finite or nan lookalike. |
