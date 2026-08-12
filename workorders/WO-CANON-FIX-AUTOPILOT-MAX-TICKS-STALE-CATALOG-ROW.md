# WO-CANON-FIX-AUTOPILOT-MAX-TICKS-STALE-CATALOG-ROW

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Annotate `autopilot_max_ticks_exhausted` in control-and-escalation.md's escalation
catalog as inventory-only / unproduced (matches operator-cold-start tip honesty).

## Accept

- Catalog row no longer reads as a live tip depletion-stop producer.
- Docs-only; no code change to stopbanner label map.

## Proof

```bash
rg -n 'autopilot_max_ticks_exhausted' canon/architecture/control-and-escalation.md
```

live-prove: n/a (docs-only).
