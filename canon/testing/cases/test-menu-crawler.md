---
type: Reference
title: Test Cases — Menu Crawler
description: Menu Crawler tests (TW-26) -- no network, mock/fixture screens only.
resource: repo://tw2002-aiclient/tests/test_menu_crawler.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_menu_crawler.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Menu Crawler tests (TW-26) -- no network, mock/fixture screens only._

| Test | Blurb |
|------|-------|
| `test_classify_option_label_safe_categories` | Classify option label safe categories. |
| `test_classify_option_label_deny_categories` | Classify option label deny categories. |
| `test_classify_option_label_expanded_deny_vocabulary` | Finding 3 (2026-07-19 re-audit): a broader belt-and-suspenders. |
| `test_compound_label_naming_a_second_committing_clause_is_not_emitted` | Finding 2 (2026-07-19 re-audit): a safe-sounding FIRST clause. |
| `test_compound_safe_sounding_label_with_no_deny_word_is_still_unknown` | The structural fix's own independent value (Finding 2): a. |
| `test_compound_connector_broadened_vocabulary_is_not_emitted` | Fix 1's compound-connector broadening (2026-07-19 THIRD re-audit. |
| `test_compound_connector_with_and_plus_do_not_over_reject_common_labels` | Fix B. |
| `test_simple_single_clause_safe_labels_still_classify_safe` | A CLEAN, single-clause label with no conjunction must NOT be. |
| `test_deny_word_anchoring_catches_glued_suffix_derived_forms` | Fix 1's surviving exact repro: "Sale" reads safe-ish by its FIRST. |
| `test_round5_accepted_residual_action_and_agent_noun_forms` | FOURTH re-audit round convergence pass (2026-07-19, "no round 5"):. |
| `test_deny_word_anchoring_catches_irregular_forms` | Fix 1's irregular-form list -- these share no letter-stem with. |
| `test_fix_2_new_deny_vocabulary` | Fix 2 (2026-07-19 THIRD re-audit round) -- a KNOWN vocabulary. |
| `test_optional_banking_and_confirm_deny_vocabulary` | Convergence-pass optional additions (cipher, on-domain): withdraw/. |
| `test_optional_banking_and_confirm_words_do_not_over_reject` | The collision-check itself, made explicit: "committee" and. |
| `test_deny_word_anchoring_does_not_over_reject_common_safe_labels` | The explicit false-positive guard required alongside Fix 1: the. |
| `test_fix_a_firing_is_denied_the_same_way_mining_is` | Fix A (a common-form MISS, mack): the round-3 silent-e fix. |
| `test_fix_b_false_positives_do_not_over_reject` | Fix B (6 coverage-BLOCKER false positives, mack + cipher):. |
| `test_fix1_complete_sweep_confirmed_false_positives_are_safe` | Fix 1's 4 confirmed false positives (mack, "the complete sweep"):. |
| `test_fix1_spender_false_positive_is_safe` | The 4th confirmed FP: "spend" -> "Spender" (an agent-noun, e. |
| `test_fix2_withdrawal_is_safe` | Fix 2 (cipher): dropped "al" from "withdraw" -- "Withdrawal" is. |
| `test_fix3_accepted_and_commitment_participles_are_not_denied` | Fix 3: "Accepted"/"Commitment" no longer deny ("ed" dropped from. |
| `test_core_active_commit_verbs_still_deny_after_the_complete_sweep` | The sweep's OWN required invariant (per the dispatch): narrowing. |
| `test_classify_option_label_ambiguous_is_unknown_not_pressed` | An unrecognized label -- not matching ANY safe or deny keyword --. |
| `test_classify_option_label_bare_enter_is_never_safe` | 2026-07-19 hardening pass (second re-audit round): `key == ""`. |
| `test_classify_option_label_bare_question_mark_is_help` | Classify option label bare question mark is help. |
| `test_bare_quit_is_not_emitted` | Finding 4 (2026-07-19 re-audit): a bare "(Q)uit" ends the live. |
| `test_classify_option_label_quit_game_carve_out_is_never_safe` | A "quit" that ALSO names a full game/session exit (the real. |
| `test_safe_allowlist_and_state_changing_keys_are_disjoint` | Trivially assertable, per the TW-26 dispatch -- also asserted at. |
| `test_enumerate_options_bracket_style_glues_key_into_word` | Enumerate options bracket style glues key into word. |
| `test_enumerate_options_bare_enter_only_on_genuine_menu` | Enumerate options bare enter only on genuine menu. |
| `test_enumerate_options_dash_style` | Enumerate options dash style. |
| `test_enumerate_options_packed_line_does_not_bleed_between_options` | Enumerate options packed line does not bleed between options. |
| `test_enumerate_options_single_line_inline_confirmation_not_a_menu` | classify. |
| `test_enumerate_options_question_mark_key_not_glued` | Enumerate options question mark key not glued. |
| `test_screen_state_menu` | Screen state menu. |
| `test_screen_state_unsafe_confirm_prompt` | Screen state unsafe confirm prompt. |
| `test_screen_state_unsafe_patterns` | Screen state unsafe patterns. |
| `test_default_answer_prompt_with_chrome_is_unsafe` | Finding 1 (mack's exact adversarial repro, 2026-07-19 re-audit):. |
| `test_default_answer_prompt_with_full_chrome_and_narrative_is_unsafe` | Finding 1 (cipher's exact adversarial repro, 2026-07-19. |
| `test_screen_state_default_answer_and_free_input_prompts_are_unsafe` | Finding 1's breadth sweep: every one of these dodges the OLD. |
| `test_screen_state_other_leaf_content` | Screen state other leaf content. |
| `test_screen_state_login_gate_is_unsafe` | Screen state login gate is unsafe. |
| `test_vertical_confirm_shapes_still_classify_menu` | The RESIDUAL class Finding 3's screen-level deny-option check. |
| `test_two_option_confirm_with_a_deny_classified_option_is_unsafe` | Finding 3 (2026-07-19 THIRD re-audit round, cipher's exact. |
| `test_vertical_confirm_shapes_never_emit_any_option` | Since bare_enter is now never in SAFE_ALLOWLIST (2026-07-19. |
| `test_bare_enter_is_never_emitted_even_on_a_genuine_menu` | `emit_key_if_safe` itself, directly: a bare Enter candidate. |
| `test_emit_key_if_safe_sends_a_safe_category` | Emit key if safe sends a safe category. |
| `test_emit_key_if_safe_never_sends_a_deny_category` | Emit key if safe never sends a deny category. |
| `test_emit_key_if_safe_never_sends_an_unknown_category` | Emit key if safe never sends an unknown category. |
| `test_crawl_menus_enumerates_the_graph_into_game_knowledge` | Crawl menus enumerates the graph into game knowledge. |
| `test_crawl_menus_never_commits_across_the_whole_graph` | THE never-commit guarantee, proven trivially per the TW-26. |
| `test_crawl_menus_records_buy_option_as_unexplored_never_pressed` | Crawl menus records buy option as unexplored never pressed. |
| `test_crawl_menus_records_quit_disconnect_as_unexplored_never_pressed` | Crawl menus records quit disconnect as unexplored never pressed. |
| `test_crawl_menus_records_ordinary_quit_as_unexplored_never_pressed` | Finding 4 regression guard, at the full crawl_menus level: even. |
| `test_crawl_menus_records_ambiguous_unlabeled_key_as_unexplored` | Crawl menus records ambiguous unlabeled key as unexplored. |
| `test_crawl_menus_backs_out_of_a_screen_that_turns_out_to_be_a_confirm_prompt` | The adversarial case: pressing a SAFE-labeled key ("(D)isplay. |
| `test_crawl_menus_root_itself_unsafe_never_presses_anything` | Edge case: the world's own start context is already a. |
| `test_crawl_menus_root_yes_no_confirm_is_closed_at_the_screen_level` | End-to-end proof of Finding 3 (2026-07-19 THIRD re-audit round):. |
| `test_crawl_menus_root_accept_decline_confirm_is_also_closed_at_the_screen_level` | Convergence pass: since "accept" was added as an optional deny. |
| `test_crawl_menus_root_ok_cancel_confirm_never_presses_anything` | The genuinely still-open residual case: neither "Ok" nor "Cancel". |
| `test_crawl_menus_bare_enter_edge_uses_enter_sentinel_key` | `upsert_menu_edge` requires a non-empty `key` string -- a bare. |
| `test_crawl_menus_respects_max_nodes_rail` | Crawl menus respects max nodes rail. |
| `test_crawl_menus_never_emits_bare_enter_on_a_commit_shaped_screen` | End-to-end adversarial proof required by the TW-26 re-audit. |
