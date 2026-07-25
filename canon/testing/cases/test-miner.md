---
type: Reference
title: Test Cases — Miner
description: Profit-miner tests (DESIGN-v2 §3 v2.
resource: repo://tw2002-aiclient/tests/test_miner.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_miner.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Profit-miner tests (DESIGN-v2 §3 v2.1 item 11c, C10) -- no network,_

| Test | Blurb |
|------|-------|
| `test_mine_patterns_surfaces_the_recurring_trade_loop` | Mine patterns surfaces the recurring trade loop. |
| `test_mine_patterns_filters_out_unsupported_one_off_windows` | Mine patterns filters out unsupported one off windows. |
| `test_mine_patterns_ranks_higher_profit_pattern_first` | Two independently-recurring 2-step patterns at different profit. |
| `test_mine_patterns_never_surfaces_a_pattern_built_on_redacted_input` | Mine patterns never surfaces a pattern built on redacted input. |
| `test_mine_patterns_falls_back_to_credits_per_action_when_no_turn_spent` | Mine patterns falls back to credits per action when no turn spent. |
| `test_mine_patterns_empty_ledger_returns_empty_list` | Mine patterns empty ledger returns empty list. |
| `test_mine_patterns_normalizes_haggled_numerals_so_the_loop_still_recurs` | Live-caught: a real port haggles, so the offer amount differs. |
| `test_mine_patterns_threads_the_origin_sector_as_start_anchor` | Mine patterns threads the origin sector as start anchor. |
| `test_mine_patterns_start_anchor_none_when_rows_lack_a_sector` | Mine patterns start anchor none when rows lack a sector. |
| `test_propose_drafts_saves_the_pattern_start_anchor` | Propose drafts saves the pattern start anchor. |
| `test_propose_drafts_writes_only_profitable_top_k` | Propose drafts writes only profitable top k. |
| `test_mine_ledger_end_to_end_reads_the_given_entries_and_proposes` | Mine ledger end to end reads the given entries and proposes. |
