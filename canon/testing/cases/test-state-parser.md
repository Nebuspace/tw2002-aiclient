---
type: Reference
title: Test Cases — test_state_parser
description: Best-effort state-extraction tests — no network involved.
resource: repo://tw2002-aiclient/tests/test_state_parser.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_state_parser.py`

_Best-effort state-extraction tests — no network involved._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_extracts_sector` | Extracts sector. |
| `test_sector_anchors_to_last_match_not_a_stale_pre_warp_line` | Sector anchors to last match not a stale pre warp line. |
| `test_a_chat_line_mentioning_sector_mid_sentence_is_not_extracted` | A chat line mentioning sector mid sentence is not extracted. |
| `test_a_genuine_status_line_still_extracts_correctly` | A genuine status line still extracts correctly. |
| `test_real_sector_wins_over_a_same_screen_phantom_chat_mention` | Real sector wins over a same screen phantom chat mention. |
| `test_genuine_status_line_with_ports_sibling_is_trusted` | Genuine status line with ports sibling is trusted. |
| `test_genuine_status_line_with_warps_to_sector_sibling_is_trusted` | Genuine status line with warps to sector sibling is trusted. |
| `test_bare_sector_line_with_no_sibling_at_all_is_not_trusted` | Bare sector line with no sibling at all is not trusted. |
| `test_mid_sentence_phantom_with_no_line_start_match_is_not_trusted` | Mid sentence phantom with no line start match is not trusted. |
| `test_residual_line_isolated_forgery_in_a_narrative_block_is_not_trusted` | Residual line isolated forgery in a narrative block is not trusted. |
| `test_sector_from_command_prompt_extracts_the_bracketed_sector` | Sector from command prompt extracts the bracketed sector. |
| `test_sector_from_command_prompt_matches_the_computer_subsystem_prompt_too` | 'Computer command [TL=...]' is a superset of the plain ship prompt (classify.py's own precedent) -- the bracketed sector is extracted the same way from either. |
| `test_sector_from_command_prompt_last_match_wins_over_an_earlier_forged_prompt` | Sector from command prompt last match wins over an earlier forged prompt. |
| `test_sector_from_command_prompt_returns_none_when_absent` | The classic TWGS shape ('Command [TL=00753:0/0/0/850] (?=Help)? |
| `test_genuine_docked_commerce_report_live_captured_fixture_is_trusted` | Genuine docked commerce report live captured fixture is trusted. |
| `test_genuine_docked_commerce_report_via_column_header_alone_is_trusted` | The column header ("Items ... |
| `test_narrative_mention_of_commodities_with_no_header_or_row_shape_is_not_trusted` | Narrative mention of commodities with no header or row shape is not trusted. |
| `test_header_with_no_commodity_row_before_the_blank_line_is_not_trusted` | Header with no commodity row before the blank line is not trusted. |
| `test_a_commodity_row_after_a_blank_line_gap_does_not_vouch_for_a_stale_header` | A commodity row after a blank line gap does not vouch for a stale header. |
| `test_anchors_to_the_last_header_not_a_stale_one_above_it` | Anchors to the last header not a stale one above it. |
| `test_extracts_turns_left_from_command_prompt` | Extracts turns left from command prompt. |
| `test_tl_hhmmss_timer_shape_is_not_misread_as_zero_turns` | Regression: this live server's MBBS Gold build uses TL= for a HH:MM:SS countdown timer, not a turn count. |
| `test_extracts_turns_left_plain_phrasing` | Extracts turns left plain phrasing. |
| `test_ship_info_turns_left_label_not_forged_from_sector_line` | WO-HUD-CREDITS-TURNS-JOIN: ship-info `I` screen uses label-first 'Turns left : N'. |
| `test_extracts_credits_label_first_shape` | Extracts credits label first shape. |
| `test_extracts_credits_amount_first_shape` | Extracts credits amount first shape. |
| `test_credits_anchors_to_you_have_line_over_a_stale_offer_mention` | Credits anchors to you have line over a stale offer mention. |
| `test_credits_takes_the_last_you_have_line_when_printed_twice` | Credits takes the last you have line when printed twice. |
| `test_credits_label_first_fallback_also_anchors_to_last_match` | Credits label first fallback also anchors to last match. |
| `test_extracts_warps` | Extracts warps. |
| `test_extracts_full_paren_wrapped_warps_list_real_screen_shape` | Extracts full paren wrapped warps list real screen shape. |
| `test_warps_anchors_to_last_match_not_a_stale_pre_warp_line` | Warps anchors to last match not a stale pre warp line. |
| `test_empty_warps_line_does_not_leak_into_a_later_unrelated_line` | Empty warps line does not leak into a later unrelated line. |
| `test_split_label_warps_line_does_not_leak_into_the_following_line` | Split label warps line does not leak into the following line. |
| `test_extracts_port_commodities` | Real port-trade table shape: NAME STATUS TRADING %-OF-MAX ONBOARD -- three numbers per row, not one. |
| `test_real_captured_port_trade_screen_fixture` | Regression: the naive single-number commodity regex misread the 'Trading' amount column (2650) as a percentage instead of the actual '% of max' column (100). |
| `test_stale_earlier_commodity_fragment_does_not_override_the_genuine_block` | Stale earlier commodity fragment does not override the genuine block. |
| `test_forged_earlier_full_report_does_not_override_a_later_genuine_one` | Forged earlier full report does not override a later genuine one. |
| `test_missing_fields_are_simply_absent` | Missing fields are simply absent. |
| `test_parse_haggle_no_active_dialogue_is_empty` | Parse haggle no active dialogue is empty. |
| `test_parse_haggle_opening_quote_buy_direction` | Real capture: a 'buy' dialogue (the port buys from us -- we want a HIGHER price) opens with a plain restatement + the same number as the offer default. |
| `test_parse_haggle_opening_quote_sell_direction` | Real capture: a 'sell' dialogue (the port sells to us -- we want a LOWER price). |
| `test_parse_haggle_round_two_anchors_to_the_latest_requote_not_the_opening_one` | Parse haggle round two anchors to the latest requote not the opening one. |
| `test_parse_haggle_final_offer_phrasing_variant_also_anchors_to_last` | Parse haggle final offer phrasing variant also anchors to last. |
| `test_parse_haggle_current_default_absent_once_the_offer_prompt_is_gone` | Parse haggle current default absent once the offer prompt is gone. |
| `test_parse_port_report_clean_multi_sector_fixture` | The representative shape: a header, three sector rows (one with both port and warps, one warps-only, one port-only), a footer. |
| `test_parse_port_report_no_report_on_screen_returns_empty_list` | Parse port report no report on screen returns empty list. |
| `test_parse_port_report_anchors_to_the_latest_report_not_a_stale_one_in_scrollback` | Parse port report anchors to the latest report not a stale one in scrollback. |
| `test_parse_port_report_skips_a_malformed_row_without_crashing` | Parse port report skips a malformed row without crashing. |
| `test_parse_port_report_drops_a_bare_sector_row_with_no_usable_data` | A sector number alone, with neither a port nor warps segment, carries no content worth writing to the world-model. |
| `test_parse_port_report_rejects_out_of_range_percentages` | Parse port report rejects out of range percentages. |
| `test_parse_port_report_accepts_boundary_percentages_0_and_100` | Parse port report accepts boundary percentages 0 and 100. |
| `test_flyby_ports_line_records_presence_and_letter_class` | Flyby ports line records presence and letter class. |
| `test_flyby_ports_none_sets_explicit_none_to_clear_prior_flyby` | WO-TUI-CHAIN-25948-FALSE-PORT: "Ports : None" must emit port=None so write_from_state can clear a stale flyby (key-absent left ghosts). |
| `test_flyby_omitted_ports_line_on_genuine_sector_clears_port` | This server omits the Ports line when the sector has no port. |
| `test_flyby_ports_class_zero_without_letter_code_is_presence_only` | Terran (Class 0) has no CIM letter code -- presence, no class key. |
| `test_flyby_presence_merges_with_same_screen_commerce_commodities` | Flyby presence merges with same screen commerce commodities. |
| `test_fighters_aboard_from_ship_info_hfs_line` | Fighters aboard from ship info hfs line. |
| `test_fighters_aboard_from_info_label_first_line` | WO-FIGHTERS-STATUS-FRESH: ship-info `I` uses label-first 'Fighters : N'. |
| `test_fighters_aboard_from_toll_option_yours_vs_theirs` | Fighters aboard from toll option yours vs theirs. |
| `test_fighters_aboard_last_match_wins_on_ship_info` | Fighters aboard last match wins on ship info. |
| `test_fighters_aboard_absent_when_no_trustworthy_line` | Fighters aboard absent when no trustworthy line. |
