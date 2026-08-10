---
type: Reference
title: Test Cases — test_menu_crawler
description: Menu Crawler tests (TW-26) -- no network, mock/fixture screens only.
resource: repo://tw2002-aiclient/tests/test_menu_crawler.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_menu_crawler.py`

_Menu Crawler tests (TW-26) -- no network, mock/fixture screens only._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **1** BANKED ignore (`test_crawl_start_protocol.py`; `test_analyze.py` BANK-DELETED). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_classify_option_label_safe_categories` | Classify option label safe categories. |
| `test_classify_option_label_deny_categories` | Classify option label deny categories. |
| `test_classify_option_label_expanded_deny_vocabulary` | Classify option label expanded deny vocabulary. |
| `test_compound_label_naming_a_second_committing_clause_is_not_emitted` | Finding 2 (2026-07-19 re-audit): a safe-sounding FIRST clause doesn't launder a state-changing SECOND clause. |
| `test_compound_safe_sounding_label_with_no_deny_word_is_still_unknown` | Compound safe sounding label with no deny word is still unknown. |
| `test_compound_connector_broadened_vocabulary_is_not_emitted` | Compound connector broadened vocabulary is not emitted. |
| `test_compound_connector_with_and_plus_do_not_over_reject_common_labels` | Compound connector with and plus do not over reject common labels. |
| `test_simple_single_clause_safe_labels_still_classify_safe` | A CLEAN, single-clause label with no conjunction must NOT be over-rejected by the compound check (Finding 2's own stated counter-examples). |
| `test_deny_word_anchoring_catches_glued_suffix_derived_forms` | Deny word anchoring catches glued suffix derived forms. |
| `test_round5_accepted_residual_action_and_agent_noun_forms` | Round5 accepted residual action and agent noun forms. |
| `test_deny_word_anchoring_catches_irregular_forms` | Deny word anchoring catches irregular forms. |
| `test_fix_2_new_deny_vocabulary` | Fix 2 new deny vocabulary. |
| `test_optional_banking_and_confirm_deny_vocabulary` | Convergence-pass optional additions (cipher, on-domain): withdraw/ deposit for a player_bank, commit/accept as central confirm verbs. |
| `test_optional_banking_and_confirm_words_do_not_over_reject` | Optional banking and confirm words do not over reject. |
| `test_deny_word_anchoring_does_not_over_reject_common_safe_labels` | Deny word anchoring does not over reject common safe labels. |
| `test_fix_a_firing_is_denied_the_same_way_mining_is` | Fix a firing is denied the same way mining is. |
| `test_fix_b_false_positives_do_not_over_reject` | Fix b false positives do not over reject. |
| `test_fix1_complete_sweep_confirmed_false_positives_are_safe` | Fix1 complete sweep confirmed false positives are safe. |
| `test_fix1_spender_false_positive_is_safe` | The 4th confirmed FP: "spend" -> "Spender" (an agent-noun, e.g. |
| `test_fix2_withdrawal_is_safe` | Fix2 withdrawal is safe. |
| `test_fix3_accepted_and_commitment_participles_are_not_denied` | Fix3 accepted and commitment participles are not denied. |
| `test_core_active_commit_verbs_still_deny_after_the_complete_sweep` | Core active commit verbs still deny after the complete sweep. |
| `test_classify_option_label_ambiguous_is_unknown_not_pressed` | Classify option label ambiguous is unknown not pressed. |
| `test_classify_option_label_bare_enter_is_never_safe` | Classify option label bare enter is never safe. |
| `test_classify_option_label_bare_question_mark_is_help` | Classify option label bare question mark is help. |
| `test_bare_quit_is_not_emitted` | Bare quit is not emitted. |
| `test_classify_option_label_quit_game_carve_out_is_never_safe` | Classify option label quit game carve out is never safe. |
| `test_safe_allowlist_and_state_changing_keys_are_disjoint` | Safe allowlist and state changing keys are disjoint. |
| `test_enumerate_options_bracket_style_glues_key_into_word` | Enumerate options bracket style glues key into word. |
| `test_enumerate_options_bare_enter_only_on_genuine_menu` | Enumerate options bare enter only on genuine menu. |
| `test_enumerate_options_dash_style` | Enumerate options dash style. |
| `test_enumerate_options_packed_line_does_not_bleed_between_options` | Enumerate options packed line does not bleed between options. |
| `test_enumerate_options_single_line_inline_confirmation_not_a_menu` | classify.py's own established false-positive case: an inline same-line confirmation must not count as a navigable menu (needs >=2 DIFFERENT qualifying lines). |
| `test_enumerate_options_question_mark_key_not_glued` | Enumerate options question mark key not glued. |
| `test_screen_state_menu` | Screen state menu. |
| `test_screen_state_unsafe_confirm_prompt` | Screen state unsafe confirm prompt. |
| `test_screen_state_unsafe_patterns` | Screen state unsafe patterns. |
| `test_default_answer_prompt_with_chrome_is_unsafe` | Default answer prompt with chrome is unsafe. |
| `test_default_answer_prompt_with_full_chrome_and_narrative_is_unsafe` | Default answer prompt with full chrome and narrative is unsafe. |
| `test_screen_state_default_answer_and_free_input_prompts_are_unsafe` | Screen state default answer and free input prompts are unsafe. |
| `test_screen_state_other_leaf_content` | Screen state other leaf content. |
| `test_screen_state_login_gate_is_unsafe` | Screen state login gate is unsafe. |
| `test_vertical_confirm_shapes_still_classify_menu` | Vertical confirm shapes still classify menu. |
| `test_two_option_confirm_with_a_deny_classified_option_is_unsafe` | Two option confirm with a deny classified option is unsafe. |
| `test_vertical_confirm_shapes_never_emit_any_option` | Vertical confirm shapes never emit any option. |
| `test_bare_enter_is_never_emitted_even_on_a_genuine_menu` | Bare enter is never emitted even on a genuine menu. |
| `test_emit_key_if_safe_sends_a_safe_category` | Emit key if safe sends a safe category. |
| `test_emit_key_if_safe_never_sends_a_deny_category` | Emit key if safe never sends a deny category. |
| `test_emit_key_if_safe_never_sends_an_unknown_category` | Emit key if safe never sends an unknown category. |
| `test_crawl_menus_enumerates_the_graph_into_game_knowledge` | Crawl menus enumerates the graph into game knowledge. |
| `test_crawl_menus_never_commits_across_the_whole_graph` | Crawl menus never commits across the whole graph. |
| `test_crawl_menus_records_buy_option_as_unexplored_never_pressed` | Crawl menus records buy option as unexplored never pressed. |
| `test_crawl_menus_records_quit_disconnect_as_unexplored_never_pressed` | Crawl menus records quit disconnect as unexplored never pressed. |
| `test_crawl_menus_records_ordinary_quit_as_unexplored_never_pressed` | Crawl menus records ordinary quit as unexplored never pressed. |
| `test_crawl_menus_records_ambiguous_unlabeled_key_as_unexplored` | Crawl menus records ambiguous unlabeled key as unexplored. |
| `test_crawl_menus_backs_out_of_a_screen_that_turns_out_to_be_a_confirm_prompt` | The adversarial case: pressing a SAFE-labeled key ("(D)isplay Combat Rating") unexpectedly lands on an actual purchase-confirm screen. |
| `test_crawl_menus_root_itself_unsafe_never_presses_anything` | Edge case: the world's own start context is already a confirm/purchase prompt. |
| `test_crawl_menus_root_yes_no_confirm_is_closed_at_the_screen_level` | Crawl menus root yes no confirm is closed at the screen level. |
| `test_crawl_menus_root_accept_decline_confirm_is_also_closed_at_the_screen_level` | Crawl menus root accept decline confirm is also closed at the screen level. |
| `test_crawl_menus_root_ok_cancel_confirm_never_presses_anything` | Crawl menus root ok cancel confirm never presses anything. |
| `test_crawl_menus_bare_enter_edge_uses_enter_sentinel_key` | `upsert_menu_edge` requires a non-empty `key` string -- a bare Enter (`""`) must never be passed to it directly. |
| `test_crawl_menus_respects_max_nodes_rail` | Crawl menus respects max nodes rail. |
| `test_crawl_menus_never_emits_bare_enter_on_a_commit_shaped_screen` | Crawl menus never emits bare enter on a commit shaped screen. |
