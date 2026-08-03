# WO-FORMATIONS-WRITEBACK-CANON-SWEEP — Sibling docs still said writeback was parked

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T01:44:00Z  
**Branch:** `wo/FORMATIONS-WRITEBACK-CANON-SWEEP`  
**Zone:** `tw2002-aiclient` only  
**Refs:** #326 / #330 · `world-model.md` · `planet-colonization.md`

## Goal

Docs-win: after `special-formations.md` Code reality was refreshed (#330), sibling
concepts still claimed formations membership/Genesis writeback was parked/unwired.

## Scope

- `canon/engine/world-model.md`
- `canon/strategy/planet-colonization.md`
- `workorders/WO-FORMATIONS-WRITEBACK-CANON-SWEEP.md`

## Accept

1. Neither file claims membership writeback is parked / no production caller
2. Both point at special-formations Code reality for the tip story
3. live `n/a` (docs)

## Proof

```bash
rg -n 'parked|no production caller' \
  canon/engine/world-model.md \
  canon/strategy/planet-colonization.md
# expect: no hits on the writeback lie
```
