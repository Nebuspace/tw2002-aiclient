---
type: Reference
title: Test Cases — Classify
description: Screen classifier tests: synthetic anchor coverage + a real captured.
resource: repo://tw2002-aiclient/tests/test_classify.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_classify.py`

_Screen classifier tests: synthetic anchor coverage + a real captured_

| Test | Blurb |
|------|-------|
| `test_main_command_prompt` | Main command prompt. |
| `test_computer_command_prompt_wins_over_main_command` | Regression: 'Computer command [TL=. |
| `test_pause_key` | Pause key. |
| `test_login_name` | Login name. |
| `test_login_password` | Login password. |
| `test_sector_display` | Sector display. |
| `test_warp_confirm_gate_wins_over_sector_display_body` | WO-CLASSIFY-WARP-CONFIRM: live stall mis-classed as sector_display. |
| `test_warp_confirm_stale_in_scrollback_does_not_poison_main_command` | Prompt-line gate only — Y/N left in scrollback above Command must. |
| `test_port_trade` | Port trade. |
| `test_unknown_fallback` | Unknown fallback. |
| `test_pause_key_takes_priority_over_other_anchors_on_same_screen` | Pause key takes priority over other anchors on same screen. |
| `test_real_captured_opening_screen_fixture` | Real captured opening screen fixture. |
| `test_real_captured_game_select_menu_fixture` | Live TWGS server-level menu uses <A>/<B>/. |
| `test_real_captured_boxed_game_select_menu_variant_fixture` | A structurally DIFFERENT live TWGS game-select shape: no "select a. |
| `test_boxed_game_select_prompt_without_game_header_is_still_a_plain_menu` | Precision guard: a DIFFERENT TWGS menu (e. |
| `test_real_captured_banner_game_select_menu_variant_fixture` | A THIRD, structurally different live TWGS game-select shape: no. |
| `test_banner_game_select_with_timed_out_as_current_prompt_stays_game_select` | WO-CLASSIFY-TIMED-OUT: TWGS appends ``Timed out. |
| `test_banner_game_select_lookalike_without_the_twgs_banner_is_still_a_plain_menu` | Precision guard, mirroring the boxed-variant negative test above:. |
| `test_stale_boxed_door_select_bleeding_into_a_later_module_entry_menu_is_not_game_select` | Vector 1: a genuine boxed door-select screen (real "Game" header. |
| `test_stale_twgs_banner_bleeding_into_a_later_unrelated_utility_menu_is_not_game_select` | Vector 2: the TWGS connect-time banner (printed once) never. |
| `test_help_screen_quoting_the_banner_verbatim_plus_an_unrelated_menu_is_not_game_select` | Vector 3: no stale scrollback needed at all -- just a help/manual. |
| `test_game_as_a_table_column_header_is_not_a_boxed_game_select_header` | Vector 4: a "who's playing what" status box with a real column. |
| `test_chat_lines_mimicking_bracket_menu_shape_plus_a_game_box_is_not_game_select` | Vector 5: two players with single-letter handles chatting, whose. |
| `test_stale_boxed_game_select_body_bleeding_into_a_live_utility_menu_is_not_game_select` | The boxed variant's own game-select body (header, game list, BOTH. |
| `test_stale_banner_game_select_body_bleeding_into_a_live_utility_menu_is_not_game_select` | Same shape as the boxed vector above, applied to the non-boxed. |
| `test_inline_same_line_bracket_confirmation_is_not_a_menu` | Regression: 'Use (N)ew Name or (B)BS Name [B] ? |
| `test_dash_style_menu_anchor` | TWGS module-entry menu style: 'T - Play Trade Wars 2002', no brackets. |
| `test_classify_screen_prefers_prompt_line_over_stale_body_text` | Regression: a settled screen can still show an earlier decorative. |
| `test_classify_screen_ignores_stale_gate_text_from_a_prior_prompt` | Regression: after answering a login-name prompt, the echoed. |
| `test_classify_screen_falls_back_to_full_text_when_prompt_line_unanchored` | Classify screen falls back to full text when prompt line unanchored. |
| `test_classify_screen_empty_prompt_uses_full_text` | Classify screen empty prompt uses full text. |
| `test_ansi_prompt` | Ansi prompt. |
| `test_game_select` | Game select. |
| `test_char_create` | Char create. |
| `test_char_create_gate_checked_against_current_prompt_line` | Char create gate checked against current prompt line. |
| `test_real_cim_report_fixture_classifies_as_cim_report` | Real cim report fixture classifies as cim report. |
| `test_help_screen_quoting_a_cim_report_as_a_worked_example_is_not_cim_report` | mack's probe_poison. |
| `test_forged_chat_broadcast_quoting_a_cim_report_is_not_cim_report` | mack's probe_poison. |
| `test_cim_report_not_yet_closed_is_not_trusted` | A report still printing (header seen, no footer yet) must not be. |
| `test_cim_report_anchors_to_the_latest_report_in_scrollback` | A stale, already-closed report sitting higher in the buffer, with. |
| `test_classify_whole_text_also_recognizes_a_genuine_cim_report` | The naive whole-text classify() must agree with classify_screen(). |
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
| `test_is_probable_secret_prompt_documented_residual_no_keyword_at_all` | The documented KNOWN RESIDUAL, pinned down rather than left. |
