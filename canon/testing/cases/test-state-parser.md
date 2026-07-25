---
type: Reference
title: Test Cases — State Parser
description: Best-effort state-extraction tests — no network involved.
resource: repo://tw2002-aiclient/tests/test_state_parser.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_state_parser.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Best-effort state-extraction tests — no network involved._

| Test | Blurb |
|------|-------|
| `test_extracts_sector` | Extracts sector. |
| `test_sector_anchors_to_last_match_not_a_stale_pre_warp_line` | Regression (DESIGN-v2 §8 root-fix): parse_state() used to. |
| `test_a_chat_line_mentioning_sector_mid_sentence_is_not_extracted` | Adapted from mack's probe_f2_carveout. |
| `test_a_genuine_status_line_still_extracts_correctly` | The real system status line ('Sector : N', its own line) must. |
| `test_real_sector_wins_over_a_same_screen_phantom_chat_mention` | Adapted from mack's probe_f2_combined. |
| `test_genuine_status_line_with_ports_sibling_is_trusted` | Genuine status line with ports sibling is trusted. |
| `test_genuine_status_line_with_warps_to_sector_sibling_is_trusted` | Genuine status line with warps to sector sibling is trusted. |
| `test_bare_sector_line_with_no_sibling_at_all_is_not_trusted` | A line-start "Sector : N" with nothing status-shaped immediately. |
| `test_mid_sentence_phantom_with_no_line_start_match_is_not_trusted` | Mid sentence phantom with no line start match is not trusted. |
| `test_residual_line_isolated_forgery_in_a_narrative_block_is_not_trusted` | mack round-3's confirmed repro (probe_residual_line_anchor. |
| `test_sector_from_command_prompt_extracts_the_bracketed_sector` | This live server's real shape: 'Command [TL=HH:MM:SS]:[NNNN] . |
| `test_sector_from_command_prompt_matches_the_computer_subsystem_prompt_too` | 'Computer command [TL=. |
| `test_sector_from_command_prompt_last_match_wins_over_an_earlier_forged_prompt` | LAST-match anchored, same forgery-resistance precedent as. |
| `test_sector_from_command_prompt_returns_none_when_absent` | The classic TWGS shape ('Command [TL=00753:0/0/0/850] (? |
| `test_genuine_docked_commerce_report_live_captured_fixture_is_trusted` | The real live-captured shape (crawl_sac, tradewarsacademy game D,. |
| `test_genuine_docked_commerce_report_via_column_header_alone_is_trusted` | The column header ("Items . |
| `test_narrative_mention_of_commodities_with_no_header_or_row_shape_is_not_trusted` | Shape-not-keyword: narrative text merely NAMING commodities (the. |
| `test_header_with_no_commodity_row_before_the_blank_line_is_not_trusted` | A header/column-header line alone, with nothing row-shaped in the. |
| `test_a_commodity_row_after_a_blank_line_gap_does_not_vouch_for_a_stale_header` | The 'immediately beneath, before the next blank line' scoping. |
| `test_anchors_to_the_last_header_not_a_stale_one_above_it` | Same stale-scrollback discipline as `is_genuine_sector_status`: a. |
| `test_extracts_turns_left_from_command_prompt` | Extracts turns left from command prompt. |
| `test_tl_hhmmss_timer_shape_is_not_misread_as_zero_turns` | Regression: this live server's MBBS Gold build uses TL= for a. |
| `test_extracts_turns_left_plain_phrasing` | This live server never actually shows TL= as a turn count (see. |
| `test_ship_info_turns_left_label_not_forged_from_sector_line` | WO-HUD-CREDITS-TURNS-JOIN: ship-info `I` screen uses label-first. |
| `test_extracts_credits_label_first_shape` | Extracts credits label first shape. |
| `test_extracts_credits_amount_first_shape` | Regression: the real screen format is amount-first ('You have. |
| `test_credits_anchors_to_you_have_line_over_a_stale_offer_mention` | Regression (DESIGN-v2 §8 root-fix -- corrupted one live reward. |
| `test_credits_takes_the_last_you_have_line_when_printed_twice` | Regression: a completed-transaction screen prints 'You have N. |
| `test_credits_label_first_fallback_also_anchors_to_last_match` | The fallback shapes (no 'you have' phrasing anywhere in the. |
| `test_extracts_warps` | Extracts warps. |
| `test_extracts_full_paren_wrapped_warps_list_real_screen_shape` | WO-FA1 regression: the real live-server shape wraps each. |
| `test_warps_anchors_to_last_match_not_a_stale_pre_warp_line` | Same stale-scrollback discipline as sector/credits above: an OLD. |
| `test_empty_warps_line_does_not_leak_into_a_later_unrelated_line` | CRITICAL regression (mack/cipher adversarial re-verify, WO-FA1. |
| `test_split_label_warps_line_does_not_leak_into_the_following_line` | CRITICAL regression, completed (cipher re-verify, WO-FA1 final. |
| `test_extracts_port_commodities` | Real port-trade table shape: NAME STATUS TRADING %-OF-MAX ONBOARD. |
| `test_real_captured_port_trade_screen_fixture` | Regression: the naive single-number commodity regex misread the. |
| `test_stale_earlier_commodity_fragment_does_not_override_the_genuine_block` | cipher's poc_commodity_stale. |
| `test_forged_earlier_full_report_does_not_override_a_later_genuine_one` | cipher's poc_commodity_full. |
| `test_missing_fields_are_simply_absent` | Missing fields are simply absent. |
| `test_parse_haggle_no_active_dialogue_is_empty` | Parse haggle no active dialogue is empty. |
| `test_parse_haggle_opening_quote_buy_direction` | Real capture: a 'buy' dialogue (the port buys from us -- we want a. |
| `test_parse_haggle_opening_quote_sell_direction` | Real capture: a 'sell' dialogue (the port sells to us -- we want. |
| `test_parse_haggle_round_two_anchors_to_the_latest_requote_not_the_opening_one` | Real captured round-2: countering the opening 2,214 quote with. |
| `test_parse_haggle_final_offer_phrasing_variant_also_anchors_to_last` | Real captured second port used 'Our final offer is N credits. |
| `test_parse_haggle_current_default_absent_once_the_offer_prompt_is_gone` | The structural "resolved" signal haggle. |
| `test_parse_port_report_clean_multi_sector_fixture` | The representative shape: a header, three sector rows (one with. |
| `test_parse_port_report_no_report_on_screen_returns_empty_list` | Parse port report no report on screen returns empty list. |
| `test_parse_port_report_anchors_to_the_latest_report_not_a_stale_one_in_scrollback` | Regression-shaped (same discipline as parse_state()'s stale-sector. |
| `test_parse_port_report_skips_a_malformed_row_without_crashing` | A row with an unparseable sector token is dropped conservatively. |
| `test_parse_port_report_drops_a_bare_sector_row_with_no_usable_data` | A sector number alone, with neither a port nor warps segment,. |
| `test_parse_port_report_rejects_out_of_range_percentages` | mack's cheap-orthogonal-hardening suggestion (2026-07-19 follow-. |
| `test_parse_port_report_accepts_boundary_percentages_0_and_100` | Parse port report accepts boundary percentages 0 and 100. |
| `test_flyby_ports_line_records_presence_and_letter_class` | Flyby ports line records presence and letter class. |
| `test_flyby_ports_none_sets_explicit_none_to_clear_prior_flyby` | WO-TUI-CHAIN-25948-FALSE-PORT: "Ports : None" must emit port=None. |
| `test_flyby_omitted_ports_line_on_genuine_sector_clears_port` | This server omits the Ports line when the sector has no port. |
| `test_flyby_ports_class_zero_without_letter_code_is_presence_only` | Terran (Class 0) has no CIM letter code -- presence, no class key. |
| `test_flyby_presence_merges_with_same_screen_commerce_commodities` | Flyby presence merges with same screen commerce commodities. |
| `test_fighters_aboard_from_ship_info_hfs_line` | Fighters aboard from ship info hfs line. |
| `test_fighters_aboard_from_info_label_first_line` | WO-FIGHTERS-STATUS-FRESH: ship-info `I` uses label-first 'Fighters : N'. |
| `test_fighters_aboard_from_toll_option_yours_vs_theirs` | Fighters aboard from toll option yours vs theirs. |
| `test_fighters_aboard_last_match_wins_on_ship_info` | Fighters aboard last match wins on ship info. |
| `test_fighters_aboard_absent_when_no_trustworthy_line` | Fighters aboard absent when no trustworthy line. |
