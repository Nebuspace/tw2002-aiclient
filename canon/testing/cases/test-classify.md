---
type: Reference
title: Test Cases — test_classify
description: Screen classifier tests: synthetic anchor coverage + a real captured TWGS screen fixture (see tests/fixtures/, captured live (historical DoD from retired root DESIGN.md §12; owning concepts: session-engine / screen-understanding)).
resource: repo://tw2002-aiclient/tests/test_classify.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_classify.py`

_Screen classifier tests: synthetic anchor coverage + a real captured TWGS screen fixture (see tests/fixtures/, captured live (historical DoD; owning concepts: session-engine / screen-understanding))._

| Test | Blurb |
|------|-------|
| `test_main_command_prompt` | Main command prompt. |
| `test_computer_command_prompt_wins_over_main_command` | Computer command prompt wins over main command. |
| `test_pause_key` | Pause key. |
| `test_login_name` | Login name. |
| `test_login_password` | Login password. |
| `test_sector_display` | Sector display. |
| `test_warp_confirm_gate_wins_over_sector_display_body` | WO-CLASSIFY-WARP-CONFIRM: live stall mis-classed as sector_display because Sector: still sat above the Y/N — gate on the prompt line must win. |
| `test_warp_confirm_stale_in_scrollback_does_not_poison_main_command` | Prompt-line gate only — Y/N left in scrollback above Command must not steal the live classification. |
| `test_port_trade` | Port trade. |
| `test_unknown_fallback` | Unknown fallback. |
| `test_pause_key_takes_priority_over_other_anchors_on_same_screen` | Pause key takes priority over other anchors on same screen. |
| `test_real_captured_opening_screen_fixture` | Real captured opening screen fixture. |
| `test_real_captured_game_select_menu_fixture` | Live TWGS server-level menu uses <A>/<B>/... |
| `test_real_captured_boxed_game_select_menu_variant_fixture` | Real captured boxed game select menu variant fixture. |
| `test_boxed_game_select_prompt_without_game_header_is_still_a_plain_menu` | Precision guard: a DIFFERENT TWGS menu (e.g. |
| `test_real_captured_banner_game_select_menu_variant_fixture` | Real captured banner game select menu variant fixture. |
| `test_banner_game_select_with_timed_out_as_current_prompt_stays_game_select` | Banner game select with timed out as current prompt stays game select. |
| `test_banner_game_select_lookalike_without_the_twgs_banner_is_still_a_plain_menu` | Banner game select lookalike without the twgs banner is still a plain menu. |
| `test_stale_boxed_door_select_bleeding_into_a_later_module_entry_menu_is_not_game_select` | Stale boxed door select bleeding into a later module entry menu is not game select. |
| `test_stale_twgs_banner_bleeding_into_a_later_unrelated_utility_menu_is_not_game_select` | Vector 2: the TWGS connect-time banner (printed once) never scrolls off / clears; a LATER, unrelated generic-prompt menu (e.g. |
| `test_help_screen_quoting_the_banner_verbatim_plus_an_unrelated_menu_is_not_game_select` | Help screen quoting the banner verbatim plus an unrelated menu is not game select. |
| `test_game_as_a_table_column_header_is_not_a_boxed_game_select_header` | Game as a table column header is not a boxed game select header. |
| `test_chat_lines_mimicking_bracket_menu_shape_plus_a_game_box_is_not_game_select` | Chat lines mimicking bracket menu shape plus a game box is not game select. |
| `test_stale_boxed_game_select_body_bleeding_into_a_live_utility_menu_is_not_game_select` | Stale boxed game select body bleeding into a live utility menu is not game select. |
| `test_stale_banner_game_select_body_bleeding_into_a_live_utility_menu_is_not_game_select` | Stale banner game select body bleeding into a live utility menu is not game select. |
| `test_inline_same_line_bracket_confirmation_is_not_a_menu` | Regression: 'Use (N)ew Name or (B)BS Name [B] ?' has two bracket pairs on ONE line -- an inline confirmation, not a genuine multi-line options list. |
| `test_dash_style_menu_anchor` | TWGS module-entry menu style: 'T - Play Trade Wars 2002', no brackets. |
| `test_classify_screen_prefers_prompt_line_over_stale_body_text` | Regression: a settled screen can still show an earlier decorative '[Pause]' marker above an already-active menu prompt. |
| `test_classify_screen_ignores_stale_gate_text_from_a_prior_prompt` | Regression: after answering a login-name prompt, the echoed 'What is your name? |
| `test_classify_screen_falls_back_to_full_text_when_prompt_line_unanchored` | Classify screen falls back to full text when prompt line unanchored. |
| `test_classify_screen_empty_prompt_uses_full_text` | Classify screen empty prompt uses full text. |
| `test_ansi_prompt` | Ansi prompt. |
| `test_game_select` | Game select. |
| `test_char_create` | Char create. |
| `test_char_create_gate_checked_against_current_prompt_line` | Char create gate checked against current prompt line. |
| `test_real_cim_report_fixture_classifies_as_cim_report` | Real cim report fixture classifies as cim report. |
| `test_help_screen_quoting_a_cim_report_as_a_worked_example_is_not_cim_report` | Help screen quoting a cim report as a worked example is not cim report. |
| `test_forged_chat_broadcast_quoting_a_cim_report_is_not_cim_report` | Forged chat broadcast quoting a cim report is not cim report. |
| `test_cim_report_not_yet_closed_is_not_trusted` | Cim report not yet closed is not trusted. |
| `test_cim_report_anchors_to_the_latest_report_in_scrollback` | Cim report anchors to the latest report in scrollback. |
| `test_classify_whole_text_also_recognizes_a_genuine_cim_report` | The naive whole-text classify() must agree with classify_screen() on a genuine report -- both call the same structural check, just with different arguments. |
| `test_is_probable_secret_prompt_matches_password` | Is probable secret prompt matches password. |
| `test_is_probable_secret_prompt_matches_pin` | Is probable secret prompt matches pin. |
| `test_is_probable_secret_prompt_matches_passcode_variants` | Is probable secret prompt matches passcode variants. |
| `test_is_probable_secret_prompt_matches_access_code` | Is probable secret prompt matches access code. |
| `test_is_probable_secret_prompt_matches_a_bare_code_prompt` | Is probable secret prompt matches a bare code prompt. |
| `test_is_probable_secret_prompt_matches_verify` | Is probable secret prompt matches verify. |
| `test_is_probable_secret_prompt_matches_secret` | Is probable secret prompt matches secret. |
| `test_is_probable_secret_prompt_is_case_insensitive` | Is probable secret prompt is case insensitive. |
| `test_is_probable_secret_prompt_word_boundary_avoids_pin_substring_false_positives` | Is probable secret prompt word boundary avoids pin substring false positives. |
| `test_is_probable_secret_prompt_false_for_ordinary_command_prompt` | Is probable secret prompt false for ordinary command prompt. |
| `test_is_probable_secret_prompt_false_for_empty_or_missing_prompt` | Is probable secret prompt false for empty or missing prompt. |
| `test_is_probable_secret_prompt_documented_residual_no_keyword_at_all` | Is probable secret prompt documented residual no keyword at all. |
