# WO-FORMATIONS-DECISIONS-PANEL — Show formations intent on DECISIONS while exploring

**Status:** OPEN · HIGH · seat `impl-aiclient-cursor`  
**Posted:** 2026-08-02T10:01Z · hub product refill (seat asked: no more stamp-only)  
**Branch:** `wo/FORMATIONS-DECISIONS-PANEL`  
**Depends:** `main` ≥ `20b4646` (#317 FORMATIONS)  
**Refs:** `formations.py` · `explore.format_explore_decision_lines` · `cockpit/decisions.py` · #317 rulings

## Goal

When Play explore is live with intent `find_formations`, the DECISIONS pane should show honest formations-oriented lines (intent + next hop / panel summary), not only the calm empty coach state. Reuse existing composers (`format_explore_decision_lines` and/or formations panel producers from #317) — **wire**, do not invent a second formatter.

## Scope

1. Product path: explore run with `INTENT_FIND_FORMATIONS` → DECISIONS lines include formations signal (count and/or next sector) via existing world_stats / explore wire fields.
2. Pins: explore+formations intent shows non-empty decisions when catalog has dead-ends; honest empty when none; no E-cycle widen (#247).
3. Tests + STATUS.

## Out of scope

- Diversity live arm (Max-gated) — suite + safe offline pins Accept-sufficient; live-prove DEFERRED → Cursor safe-half optional.
- Canon prose Max-gated banks.

## Accept

1. Product caller reaches formations/explore decision lines while `find_formations` explore is active.
2. Suite green with pins; no `twclient`.
3. STATUS cites call path file:line.

## Proof

Suite. `live-prove`: n/a or safe-half per hub GO if you touch money-path arm (prefer offline).
