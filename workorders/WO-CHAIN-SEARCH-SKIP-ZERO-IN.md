# WO-CHAIN-SEARCH-SKIP-ZERO-IN

**Goal:** Stop the N-port cycle finder from burning its DFS budget on
in-degree-0 starts (e.g. SSS all-selling ports), so priced multi-hop
chains surface in the Trade Loop Chain bubbles instead of falling back
to a 2-port class pair when real cycles exist.

## Symptom (Max 2026-07-31)

Passed three sectors with ports in a row; bubble still showed a
**2-sector** chain (`class pair` caption).

## Root cause (hub-measured, academy Sextant @ `dd8222f`)

1. `build_trade_hops` → **120** positive-margin hops.
2. `find_profit_chains_with_note` → **0** chains, `search_note` =
   budget exhausted at 100k DFS steps, **0/11 starts completed**.
3. First start in insertion order was **SSS 3076** (`out=22`, `in=0`).
   A cycle that starts at S must hop back to S — in-degree 0 can never
   close. Searching from it only explores an open tree.
4. Raising budget to 2M (or reordering to prefer `in>0`) finds **3000+**
   chains (up to 9 hops). UI had empty priced result → **class pair
   fallback** (always exactly two ports by design).

Also: three ports on a walk ≠ a 3-bubble priced cycle. A recent path
with two SSS (buy-from-only) cannot close a trade loop through those
SSS nodes.

## Fix

In `chains._search_cycles`:

- Compute in-degree while building `adj`.
- **Skip** starts with `in_degree == 0`.
- Sort remaining starts by ascending out-degree (then descending
  in-degree) so tight pairs surface before wide trees.

## Accept

1. New unit pin:
   `test_in_degree_zero_start_does_not_starve_budget_for_real_pairs`.
2. Existing `tests/test_chains.py` + `tests/test_chain_search.py` green.
3. Live academy (or copied world):
   `chain_search.recompute` returns `reason is None` and
   `len(best.hops) >= 2` while positive mutual hops exist — not an empty
   truncated search that forces class-pair bubbles.
4. Bubbles prefer priced `best_chain` over `class pair` when chains
   exist (existing `bubble_subject` precedence — no UI change required).

## Scope

- `tw2002_aiclient/chains.py`
- `tests/test_chains.py`
- `workorders/WO-CHAIN-SEARCH-SKIP-ZERO-IN.md`

## Out of bounds

- Do not invent margin on class pairs.
- Do not change `CandidatePair` to N-port (separate product decision).
- Do not raise `DEFAULT_MAX_SEARCH_STEPS` as the primary fix (skip is
  correct; budget remains a backstop).

## Proof

- Offline: pytest pins above.
- Live: hub/seat probe on connected academy world — dump
  `recompute` reason + top chain hop-count + bubble caption.
