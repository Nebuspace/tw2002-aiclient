---
type: Reference
title: Test Cases — test_chains
description: TW-21 longest-profit-chain algorithm tests (synthetic graphs).
resource: repo://tw2002-aiclient/tests/test_chains.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:00Z
---

# Test Cases — `tests/test_chains.py`

_TW-21 longest-profit-chain algorithm tests (synthetic graphs)._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; un-ignored via WO-CHAIN-DETECT-PORT rehab — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.

| Test | Blurb |
|------|-------|
| `test_triangle_longest_and_callout` | Triangle longest and callout. |
| `test_negative_hop_breaks_triangle` | Negative hop breaks triangle. |
| `test_longer_cycle_preferred_over_shorter_higher_cprt` | Longer cycle preferred over shorter higher cprt. |
| `test_tie_on_length_higher_cr_per_turn_wins` | Tie on length higher cr per turn wins. |
| `test_empty_hops` | Empty hops. |
| `test_library_row_bridge` | Library row bridge. |
