---
type: Reference
title: Test Cases — Cockpit Viewport Paint
description: Layer-A tests for the GAME viewport paint composer (WO-P4-052).
resource: repo://tw2002-aiclient/tests/test_cockpit_viewport_paint.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_viewport_paint.py`

_Layer-A tests for the GAME viewport paint composer (WO-P4-052)._

| Test | Blurb |
|------|-------|
| `test_fixture_grid_composes_to_exact_expected_lines` | Fixture grid composes to exact expected lines. |
| `test_over_wide_rows_clip_to_width` | Over wide rows clip to width. |
| `test_over_tall_input_keeps_last_height_rows_top_drop` | Over tall input keeps last height rows top drop. |
| `test_exactly_fitting_input_is_unchanged` | Exactly fitting input is unchanged. |
| `test_under_height_input_is_unchanged_no_padding` | Under height input is unchanged no padding. |
| `test_none_event_is_honest_empty` | None event is honest empty. |
| `test_non_dict_event_is_honest_empty` | Non dict event is honest empty. |
| `test_missing_screen_key_is_honest_empty` | Missing screen key is honest empty. |
| `test_screen_not_a_list_is_honest_empty` | Screen not a list is honest empty. |
| `test_a_single_non_str_row_invalidates_the_whole_grid` | A single non str row invalidates the whole grid. |
| `test_width_or_height_non_positive_is_empty` | Width or height non positive is empty. |
| `test_hostile_width_height_types_degrade_to_empty_not_raise` | Hostile width height types degrade to empty not raise. |
| `test_draw_calls_viewport_provider_exactly_once_and_paints_its_content` | Draw calls viewport provider exactly once and paints its content. |
| `test_draw_paints_nothing_when_no_provider_set` | Matches PWO-051's own contract, re-proven here at the paint call. |
| `test_draw_paints_nothing_when_provider_returns_none_event` | Draw paints nothing when provider returns none event. |
| `test_raising_provider_does_not_crash_draw_and_leaves_interior_blank` | Raising provider does not crash draw and leaves interior blank. |
| `test_provider_returning_object_without_latest_event_does_not_crash_draw` | A provider that doesn't honor the ``WatchFeedSnapshot`` duck-type. |
