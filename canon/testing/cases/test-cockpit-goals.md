---
type: Reference
title: Test Cases — Cockpit Goals
description: Pure GOALS-panel composer tests (PWO-034, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_goals.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_goals.py`

_Pure GOALS-panel composer tests (PWO-034, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_status_none_all_nine_lines_unknown` | Status none all nine lines unknown. |
| `test_status_empty_dict_matches_none` | Status empty dict matches none. |
| `test_empty_state_never_vanishes_rows` | Empty state never vanishes rows. |
| `test_full_fixture_wide_width_exact_lines` | Full fixture wide width exact lines. |
| `test_full_fixture_narrow_width_uses_short_labels` | Full fixture narrow width uses short labels. |
| `test_canon_order_is_fixed_regardless_of_dict_key_order` | Canon order is fixed regardless of dict key order. |
| `test_stardock_not_found_blocks_ship_and_hold_price` | Stardock not found blocks ship and hold price. |
| `test_stardock_unknown_does_not_block_ship_and_hold_price` | Stardock unknown does not block ship and hold price. |
| `test_stardock_found_without_sectors_list` | Stardock found without sectors list. |
| `test_stardock_sectors_list_caps_at_three` | Stardock sectors list caps at three. |
| `test_map_known_sectors_without_galaxy_size` | Map known sectors without galaxy size. |
| `test_map_fully_explored_shows_met_glyph` | Map fully explored shows met glyph. |
| `test_formations_zero_is_unknown_glyph_not_partial` | Formations zero is unknown glyph not partial. |
| `test_formations_positive_is_partial_glyph` | Formations positive is partial glyph. |
| `test_chain_zero_hops_is_partial_not_unknown` | Chain zero hops is partial not unknown. |
| `test_ship_prices_zero_is_partial_price_unknown` | Ship prices zero is partial price unknown. |
| `test_hold_price_blank_string_key_present_is_partial` | Hold price blank string key present is partial. |
| `test_fighters_zero_shows_default_buy_status` | Fighters zero shows default buy status. |
| `test_fighters_zero_shows_supplied_buy_status` | Fighters zero shows supplied buy status. |
| `test_fighters_positive_count` | Fighters positive count. |
| `test_malformed_values_never_raise_and_degrade_to_unknown` | Malformed values never raise and degrade to unknown. |
| `test_raising_int_on_turns_left_never_raises` | Raising int on turns left never raises. |
| `test_non_finite_float_on_every_int_field_never_raises` | Non finite float on every int field never raises. |
| `test_stardock_sectors_entry_with_raising_str_never_raises` | Stardock sectors entry with raising str never raises. |
| `test_status_non_dict_types_never_raise` | Status non dict types never raise. |
| `test_width_non_int_never_raises` | Width non int never raises. |
| `test_width_clip_sweep_every_line_within_budget` | Width clip sweep every line within budget. |
| `test_width_zero_or_negative_returns_all_empty_lines` | Width zero or negative returns all empty lines. |
| `test_narrow_width_switches_every_label_to_short_form` | Narrow width switches every label to short form. |
| `test_glyph_set_pin_no_ascii_fabrications` | Glyph set pin no ascii fabrications. |
