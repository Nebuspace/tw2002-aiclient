# WO-FIX-GOALS-CHAIN-ROW-KEYPRESS-GATED-STALE

**Status:** DONE (pending merge)
**Priority:** MED
**Gated:** no

## Goal

Stop GOALS saying `chain: none yet` while the always-on bubble strip still
shows a class-pair (or other) chain subject — Max live-observed 2026-08-05.

## Root cause (tip check)

`live_refresh` already refreshes discovery on the idle tick (budget-gated);
the queue’s “only on L” framing was partially stale. The load-bearing miss:
`_display_hops_unit` / `merge` followed priced cycles only, so a completed
empty priced search (`_hops=0` → “none yet”) plus `update_pairs` fallback
left the bubble painting a pair while GOALS disagreed.

## Scope

- `tw2002_aiclient/chain_status.py` — pair branch in `_display_hops_unit` +
  `merge` when pair exists without priced `_seen`
- `tests/test_chain_status_coach_wire.py` — pins
- This WO file

## Accept

1. Empty priced + class pair → GOALS shows hop count matching bubble, not `none yet`.
2. Pair-only (never priced-seen) → merge still supplies hops.
3. live-prove: product UX; safe half = offline pins; full live diversity deferred unless hub asks.

## Proof

`pytest tests/test_chain_status_coach_wire.py -k goals_hops_match_bubble_pair -n0`
