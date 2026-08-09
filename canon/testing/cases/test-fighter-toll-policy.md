---
type: Reference
title: Test Cases — test_fighter_toll_policy
description: WO-FIGHTER-FLOOR-TOLL — fighter reserve + Option?
resource: repo://tw2002-aiclient/tests/test_fighter_toll_policy.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_fighter_toll_policy.py`

_WO-FIGHTER-FLOOR-TOLL — fighter reserve + Option?_

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_default_reserve_is_small_and_documented` | Default reserve is small and documented. |
| `test_reserve_preserved_on_deploy_sell_clamp` | Reserve preserved on deploy sell clamp. |
| `test_parse_fighter_option_counts` | Parse fighter option counts. |
| `test_parse_ignores_non_option_screens` | Parse ignores non option screens. |
| `test_single_fighter_toll_attacks_when_reserve_allows` | Single fighter toll attacks when reserve allows. |
| `test_newplayer_toll_no_pay_prompt_attacks_favorable_odds` | WO-FIGHTER-TOLL-NEWPLAYER: live Option? |
| `test_zero_fighters_retreats_never_pay` | Folded WO-FIGHTER-AUTO-R: 0 vs 1 → R, never P. |
| `test_multi_fighter_hopeless_retreats` | Multi fighter hopeless retreats. |
| `test_few_enemies_but_outgunned_retreats` | Few enemies but outgunned retreats. |
| `test_unparsed_option_retreats_safe` | WO-OPTION-CLEAR-ENSURE: Option? |
| `test_toll_banner_without_vs_line_still_detects_theirs` | Toll banner without vs line still detects theirs. |
| `test_attack_qty_prompt_preferred_over_option` | Live Ona: qty prompt + stale Option? |
| `test_attack_qty_uses_max_when_counts_missing` | Attack qty uses max when counts missing. |
| `test_pay_is_never_selected_even_when_the_key_is_offered` | Decide never selects Pay even when the Pay key is offered on-screen. |
| `test_parse_fighter_option_does_not_detect_from_scrollback_when_prompt_line_given` | Accept-3 root: after Retreat the Option? |
| `test_parse_attack_qty_does_not_detect_from_scrollback_when_prompt_line_given` | Sibling to the Option? |
