# WO-CANON-FIX-TRADE-DRIVER-OPEN-GAP-RESOLVED

**Status:** OPEN → this PR  
**gated:** no  
**schema:** n/a (docs only)

## Goal

Tip-true the audit-cycle-6 DRAFT-CANON honesty fixes: stop listing `trade_driver`'s
autonomous chain runner as an open Code-divergence gap in
`port-economics.md` / `exploration-policy.md`, and name `force_share_auto_attack`
as Max-ratified in `action-safety-guards.md`.

## Verify-first (2026-08-10 against `origin/main` @ `1663f79`)

- `trade_driver.py`: `_confirmed_send` (~L359) fails closed on `ctx.armed()`;
  `_navigate` (~L764) re-validates `classify_screen` before warp sends;
  `_visit_port` present — gap is closed on tip, docs lagged.
- `DECISIONS.md` carries `RESOLVED-COMBAT-AUTOFIGHT-90` (2026-07-28) for
  `force_share ≥ 0.90`.
- Chain-hunt "in tip" citation after PR #640/#641 must stay (do not regress).

## Scope

- `canon/strategy/port-economics.md`
- `canon/strategy/exploration-policy.md`
- `canon/doctrine/action-safety-guards.md`
- `workorders/WO-CANON-FIX-TRADE-DRIVER-OPEN-GAP-RESOLVED.md` (this file)

## Accept

1. Both strategy docs mark the trade_driver chain-runner divergence **RESOLVED**
   with tip citations (`_navigate` / `_confirmed_send` / armed fail-closed).
2. `action-safety-guards.md` cites `RESOLVED-COMBAT-AUTOFIGHT-90` for
   `force_share_auto_attack`.
3. Exploration-policy Chain-hunt bullet remains **in tip** (no regression of #641).

## Proof

Docs-only. `git grep` for the old "open gap" trade_driver framing returns empty
in the three scoped files; suite / live-prove n/a.

## Origin

Hub audit-cycle-6 (2026-08-09T15:27Z) DRAFT-CANON batch — staged locally on hub
main, never pushed. This WO lands the tip-true slice without the stale ADR-003
regression that sat beside it in that dirty tree.
