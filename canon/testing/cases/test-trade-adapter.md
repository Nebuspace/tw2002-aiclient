---
type: Reference
title: Test Cases — test_trade_adapter
description: WO-FA3 trade_adapter tests -- synthetic world-model fixtures only, no live daemon, no network (same tmp_path/state_dir convention as test_world_model.py).
resource: repo://tw2002-aiclient/tests/test_trade_adapter.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_trade_adapter.py`

_WO-FA3 trade_adapter tests -- synthetic world-model fixtures only, no live daemon, no network (same tmp_path/state_dir convention as test_world_model.py)._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_direction_compatible_pair_hand_computed_margins_and_best_chain` | Direction compatible pair hand computed margins and best chain. |
| `test_both_ports_selling_same_commodity_yields_zero_hops` | Both ports selling same commodity yields zero hops. |
| `test_both_ports_buying_same_commodity_yields_zero_hops` | Both ports buying same commodity yields zero hops. |
| `test_missing_status_field_yields_zero_hops` | Missing status field yields zero hops. |
| `test_unrecognized_commodity_name_yields_zero_hops` | No configured floor price -> `_commodity_price` returns None -> never a guessed margin. |
| `test_no_known_route_yields_no_hop` | No known route yields no hop. |
| `test_multi_hop_turns_is_path_length_minus_one` | Multi hop turns is path length minus one. |
| `test_stale_port_reading_is_dropped` | Stale port reading is dropped. |
| `test_fresh_port_reading_within_max_age_is_kept` | Sanity counterpart to the stale test above -- the freshness gate doesn't drop everything, just genuinely stale readings. |
| `test_hop_cap_truncates_and_reports_a_note` | Hop cap truncates and reports a note. |
| `test_empty_world_returns_empty_and_no_note` | Empty world returns empty and no note. |
| `test_single_port_world_returns_empty` | Single port world returns empty. |
| `test_empty_hops_keeps_chain_finder_output_none` | Empty hops keeps chain finder output none. |
| `test_non_dict_port_is_skipped_not_crashed` | Non dict port is skipped not crashed. |
| `test_non_list_commodities_is_skipped_not_crashed` | Non list commodities is skipped not crashed. |
| `test_non_dict_commodity_row_is_skipped_but_sibling_valid_row_still_works` | Non dict commodity row is skipped but sibling valid row still works. |
| `test_unhashable_commodity_name_row_is_skipped_not_crashed` | Unhashable commodity name row is skipped not crashed. |
| `test_non_numeric_sector_id_field_is_skipped_not_crashed` | Non numeric sector id field is skipped not crashed. |
| `test_non_finite_pct_yields_no_hop` | Non finite pct yields no hop. |
| `test_max_hops_zero_returns_empty_but_notes_the_drop` | Max hops zero returns empty but notes the drop. |
| `test_negative_max_hops_raises_at_construction` | Negative max hops raises at construction. |
| `test_both_sides_zero_amount_yields_no_hop` | Both sides zero amount yields no hop. |
| `test_empty_seller_zero_amount_yields_no_hop` | Empty seller zero amount yields no hop. |
| `test_empty_buyer_zero_amount_yields_no_hop` | Empty buyer zero amount yields no hop. |
| `test_both_sides_above_default_floor_emits_hop` | Both sides above default floor emits hop. |
| `test_amount_below_configured_floor_is_dropped` | Amount below configured floor is dropped. |
| `test_amount_above_configured_floor_still_emits_hop` | Amount above configured floor still emits hop. |
| `test_missing_or_unusable_amount_yields_no_hop` | Missing or unusable amount yields no hop. |
