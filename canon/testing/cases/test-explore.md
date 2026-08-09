---
type: Reference
title: Test Cases — test_explore
description: TW-14 Map-fill / frontier explore planner tests.
resource: repo://tw2002-aiclient/tests/test_explore.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_explore.py`

_TW-14 Map-fill / frontier explore planner tests._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_frontier_finds_unmapped_neighbor` | Frontier finds unmapped neighbor. |
| `test_exhausted_when_fully_mapped` | Exhausted when fully mapped. |
| `test_zero_budget_exhausts_even_with_frontier` | Zero budget exhausts even with frontier. |
| `test_epsilon_can_pick_deeper_edge` | Epsilon can pick deeper edge. |
| `test_find_stardock_landmark` | Find stardock landmark. |
| `test_path_to_sector` | Path to sector. |
| `test_frontier_edges_unit` | Frontier edges unit. |
| `test_find_stardock_routes_when_landmark_known` | Find stardock routes when landmark known. |
| `test_find_stardock_arrived` | Find stardock arrived. |
| `test_find_stardock_hunts_via_map_fill` | Find stardock hunts via map fill. |
| `test_find_stardock_hunt_resolves_a_multi_hop_frontier_to_the_first_adjacent_step` | Find stardock hunt resolves a multi hop frontier to the first adjacent step. |
| `test_find_formations_routes_to_dead_end` | Find formations routes to dead end. |
| `test_cycle_explore_mode_and_decision_lines` | Cycle explore mode and decision lines. |
| `test_plan_map_fill_prefers_port_neighborhood_over_nearer_unrelated` | Accept-2 WO-PORT-CHAIN-SEED: seeded port fringe beats a depth-1 unrelated hop. |
| `test_plan_map_fill_falls_back_to_nearest_when_no_port_seeds` | Plan map fill falls back to nearest when no port seeds. |
| `test_exhausted_recovery_warps_toward_densest_hub` | WO-EXPLORE-NO-CANDIDATES: fully mapped component → densest hop. |
| `test_exhausted_recovery_prefers_stardock_when_landmark_known` | Exhausted recovery prefers stardock when landmark known. |
| `test_exhausted_recovery_halts_when_already_at_densest` | Exhausted recovery halts when already at densest. |
