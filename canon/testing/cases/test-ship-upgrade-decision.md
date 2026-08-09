---
type: Reference
title: Test Cases — test_ship_upgrade_decision
description: TW-30 ship-upgrade decision engine — unit coverage for all five §24 learnings.
resource: repo://tw2002-aiclient/tests/test_ship_upgrade_decision.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_ship_upgrade_decision.py`

_TW-30 ship-upgrade decision engine — unit coverage for all five §24 learnings._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_remaining_productive_turns_respects_reserve` | Remaining productive turns respects reserve. |
| `test_roi_vs_budget_57_turns_rejects_250_hold` | §24 key fix: 57 turns left → do NOT recommend a 250-hold upgrade. |
| `test_alignment_rank_filter_blocks_uncommissioned` | Alignment rank filter blocks uncommissioned. |
| `test_holds_per_turn_ranks_galleon_above_barge` | Holds per turn ranks galleon above barge. |
| `test_choose_upgrade_picks_better_warp_at_equal_holds` | Choose upgrade picks better warp at equal holds. |
| `test_loop_stock_match_flags_needs_chains` | Loop stock match flags needs chains. |
| `test_defense_floor_on_hostile_server` | Defense floor on hostile server. |
| `test_defense_floor_ignored_on_peaceful` | Defense floor ignored on peaceful. |
| `test_choose_upgrade_prefers_affordable_commissioned_over_slaver` | Choose upgrade prefers affordable commissioned over slaver. |
| `test_payback_turns_positive_for_upgrade` | Payback turns positive for upgrade. |
