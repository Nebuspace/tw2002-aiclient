---
type: Reference
title: Test Cases — test_screens_shared_pairs
description: Screens shared pairs.
resource: repo://tw2002-aiclient/tests/test_screens_shared_pairs.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_screens_shared_pairs.py`

_Screens shared pairs._

| Test | Blurb |
|------|-------|
| `test_no_color_support_short_circuits_to_normal_without_touching_curses` | No color support short circuits to normal without touching curses. |
| `test_both_default_never_allocates_a_pair` | Both default never allocates a pair. |
| `test_default_fg_with_real_bg_allocates_a_pair_with_minus_one_fg` | Default fg with real bg allocates a pair with minus one fg. |
| `test_real_fg_with_default_bg_allocates_a_pair_with_minus_one_bg` | Real fg with default bg allocates a pair with minus one bg. |
| `test_single_arg_call_defaults_bg_to_default_zero_behavior_change` | Single arg call defaults bg to default zero behavior change. |
| `test_same_combo_reuses_the_cached_pair_number` | Same combo reuses the cached pair number. |
| `test_distinct_combos_get_distinct_pair_numbers` | Distinct combos get distinct pair numbers. |
| `test_pyte_only_names_resolve_through_the_merged_table` | Pyte only names resolve through the merged table. |
| `test_hostile_unhashable_fg_name_does_not_crash` | Hostile unhashable fg name does not crash. |
| `test_proactive_color_pairs_limit_degrades_without_crash` | Proactive color pairs limit degrades without crash. |
| `test_exhaustion_is_cached_not_retried_every_call` | Exhaustion is cached not retried every call. |
| `test_reactive_curses_error_from_init_pair_degrades_without_crash` | Reactive curses error from init pair degrades without crash. |
| `test_color_pairs_attribute_missing_falls_back_to_reactive_check_only` | Color pairs attribute missing falls back to reactive check only. |
| `test_chrome_pair_is_init_paired_exactly_once_even_as_game_cells_allocate` | Chrome pair is init paired exactly once even as game cells allocate. |
| `test_start_color_and_use_default_colors_called_exactly_once_total` | Start color and use default colors called exactly once total. |
