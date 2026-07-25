---
type: Reference
title: Test Cases — Chains
description: TW-21 longest-profit-chain algorithm tests (synthetic graphs).
resource: repo://tw2002-aiclient/tests/test_chains.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_chains.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_TW-21 longest-profit-chain algorithm tests (synthetic graphs)._

| Test | Blurb |
|------|-------|
| `test_triangle_longest_and_callout` | Triangle longest and callout. |
| `test_negative_hop_breaks_triangle` | Negative hop breaks triangle. |
| `test_longer_cycle_preferred_over_shorter_higher_cprt` | Longer cycle preferred over shorter higher cprt. |
| `test_tie_on_length_higher_cr_per_turn_wins` | Tie on length higher cr per turn wins. |
| `test_empty_hops` | Empty hops. |
| `test_library_row_bridge` | Library row bridge. |
