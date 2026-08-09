---
type: Reference
title: Test Cases — test_miner
description: Miner.
resource: repo://tw2002-aiclient/tests/test_miner.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_miner.py`

_Miner._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_mine_patterns_surfaces_the_recurring_trade_loop` | Mine patterns surfaces the recurring trade loop. |
| `test_mine_patterns_filters_out_unsupported_one_off_windows` | Mine patterns filters out unsupported one off windows. |
| `test_mine_patterns_ranks_higher_profit_pattern_first` | Mine patterns ranks higher profit pattern first. |
| `test_mine_patterns_never_surfaces_a_pattern_built_on_redacted_input` | Mine patterns never surfaces a pattern built on redacted input. |
| `test_mine_patterns_falls_back_to_credits_per_action_when_no_turn_spent` | Mine patterns falls back to credits per action when no turn spent. |
| `test_mine_patterns_empty_ledger_returns_empty_list` | Mine patterns empty ledger returns empty list. |
| `test_mine_patterns_normalizes_haggled_numerals_so_the_loop_still_recurs` | Mine patterns normalizes haggled numerals so the loop still recurs. |
| `test_mine_patterns_threads_the_origin_sector_as_start_anchor` | Mine patterns threads the origin sector as start anchor. |
| `test_mine_patterns_start_anchor_none_when_rows_lack_a_sector` | Mine patterns start anchor none when rows lack a sector. |
| `test_propose_drafts_saves_the_pattern_start_anchor` | Propose drafts saves the pattern start anchor. |
| `test_propose_drafts_writes_only_profitable_top_k` | Propose drafts writes only profitable top k. |
| `test_mine_ledger_end_to_end_reads_the_given_entries_and_proposes` | Mine ledger end to end reads the given entries and proposes. |
