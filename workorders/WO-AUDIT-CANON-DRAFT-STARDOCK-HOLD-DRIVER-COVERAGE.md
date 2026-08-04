# WO-AUDIT-CANON-DRAFT-STARDOCK-HOLD-DRIVER-COVERAGE

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** MED
**Depends-on:** none
**Gated:** no — canon fold-in only (money-path *docs*; no execute-path code change)

## Goal

Give `stardock_hold_driver.py` + `stardock_hold_plan.py` a named canon home (safety pins,
one-pass shape) beside TW-22 auto-max-holds in ship-progression.

## Approach

Fold into [ship-progression](../canon/strategy/ship-progression.md) — already cites the plan
module for TW-22; add explicit driver section + citations.

## Scope

- `canon/strategy/ship-progression.md`
- This WO file

## Accept

1. Canon names both modules, one-pass send, refuse qty/price mismatch, no tolls / no trade_chain.
2. Cross-links Mode-leave `stardock_hold_stop` / `C)argo Hold Upgrade·ON`.
3. live-prove: `n/a` (docs-only).

## Proof

`rg stardock_hold_driver|run_hold_purchase canon/strategy/ship-progression.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-STARDOCK-HOLD-DRIVER-COVERAGE`
- `tw2002_aiclient/stardock_hold_driver.py` · `stardock_hold_plan.py`
