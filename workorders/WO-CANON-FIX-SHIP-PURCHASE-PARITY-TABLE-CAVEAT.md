# WO-CANON-FIX-SHIP-PURCHASE-PARITY-TABLE-CAVEAT

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Doc-accuracy: `action-safety-guards.md` must not read as if ship purchase shares the working
StarDock hold-upgrade execute path. Ship purchase has no tip send/confirm driver and no live
purchase-confirm capture yet.

## Accept

- Human-confirmed-irreversibles prose + Schema row distinguish LIVE hold upgrade
  (`stardock_hold_driver`) from blocked ship purchase (pending live capture; cite research).
- No policy change; docs-only.

## Proof

```bash
rg -n 'ship-purchase|stardock_hold_driver|no live' canon/doctrine/action-safety-guards.md
```

live-prove: n/a (docs-only).
