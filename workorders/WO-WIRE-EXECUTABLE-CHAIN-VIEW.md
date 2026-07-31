# WO-WIRE-EXECUTABLE-CHAIN-VIEW

**Goal:** Wire `chains.is_executable_chain` into the L)chains /
`chain_search_view` rendering so discovery-only short cycles are visibly
marked (or separated) — the helper and its canon floor already exist;
the view only *mentions* it in a docstring today.

## Why (unused-code tick 2026-07-31)

`is_executable_chain` is `symbol_test_only` in the unused sweep while
`chain_search_view._hops_text` documents: hop count “decides
`chains.is_executable_chain`. Reserved and never truncated.” — but never
calls it. Operators can see a 1-hop-shaped row as if it were an earn
macro candidate.

## Fix

In `tw2002_aiclient/chain_search_view.py` (+ pins):

1. Call `chains.is_executable_chain` (or equivalent hop-floor check using
   the same `MIN_CHAIN_LINKS_TO_EXECUTE` constant) when formatting each
   chain row.
2. Mark discovery-only rows honestly — e.g. a fixed tag / marker such as
   `discovery` (exact string pinned in tests) — without inventing margin
   or changing ranking.
3. Do **not** hide discovery-only rows by default (still useful map
   chrome); do **not** change execute/arm paths (ADR-003 approve stays
   separate).
4. Prefer importing `is_executable_chain` over re-deriving the floor so
   the ONE consumer stays the helper.

## Accept

1. Unit: a 1-hop (or below-floor) chain row includes the discovery marker;
   a ≥ floor chain does not.
2. Unit: existing format pins for empty / truncated reasons still green.
3. `pytest` on `tests/test_chain_search_view.py` (+ any new pins) green.

## Scope

- `tw2002_aiclient/chain_search_view.py`
- `tests/test_chain_search_view.py`
- `workorders/WO-WIRE-EXECUTABLE-CHAIN-VIEW.md`

## Out of bounds

- No change to `chains.py` floor constants
- No autoloop / trade_driver arm changes
- No bubble strip changes (#273/#275)

## Proof

- Offline pins above
- live-prove **n/a** (view markup; no live arm)

## Refs

- `chains.is_executable_chain` · `MIN_CHAIN_LINKS_TO_EXECUTE`
- unused-code tick propose 2026-07-31
- `.samantha/audit/UNUSED-CODE-TICK.md`
