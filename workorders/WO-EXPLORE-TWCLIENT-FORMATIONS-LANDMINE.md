# WO-EXPLORE-TWCLIENT-FORMATIONS-LANDMINE — Remove armed twclient import in explore

**Status:** OPEN · EXECUTE · HIGH · Claude Code · impl-claudecode-aiclient  
**Posted:** 2026-07-28T03:45Z · hub from CC unreachable-sweep review  
**Refs:** CC STATUS 2026-07-28T03:44:20Z · ADR-001 deleted `twclient` · `explore.py:493`

## Goal
`plan_find_formations` does `from twclient.formations import catalog_world` at **call time**.
`twclient` is gone (ADR-001). Import-time is clean; suite green; **first real caller gets
ModuleNotFoundError**. This is an armed landmine — higher priority than unreachable-complete
modules.

## Accept
1. Remove or replace the dead import path — honest refuse / NotImplemented / port to in-tree
   equivalent — **no** `twclient` import remains in product code.
2. Pin: calling `plan_find_formations` (or importing the call path) does **not** raise
   `ModuleNotFoundError: twclient`; behaviour is named and tested.
3. Grep: zero `twclient` imports in `tw2002_aiclient/` (comments/docs OK if clearly historical).
4. Suite + STATUS; live-prove n/a unless a live formations path exists (then prove refuse).

## Constraints
Do not resurrect `twclient`. Do not widen into full formations product unless Max asks.
