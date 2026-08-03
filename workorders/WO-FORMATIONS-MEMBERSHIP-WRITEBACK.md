# WO-FORMATIONS-MEMBERSHIP-WRITEBACK — Stamp formation_membership on sectors

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T00:49:30Z  
**Branch:** `wo/FORMATIONS-MEMBERSHIP-WRITEBACK`  
**Zone:** `tw2002-aiclient` only  
**Refs:** canon `special-formations.md` parked writeback · WO-FA14 · #325 full detector · `world_model.formation_membership`

## Goal

Wire the parked writeback trio's **membership** half: after a successful
formations scan, upsert canon-hyphen `formation_membership` tags onto
world-model sectors. Still LOCATE/CATALOG/RECOMMEND only — no Genesis deploy.

## Scope

- `tw2002_aiclient/formations.py` — `membership_map` / `write_membership` /
  `recommend_genesis`; best-effort write from `catalog_world`
- `tw2002_aiclient/world_stats.py` — write after successful refresh scan
- `tests/` — membership tags + world_model round-trip
- `workorders/WO-FORMATIONS-MEMBERSHIP-WRITEBACK.md` — this file

## Constraints

- Tags: canon hyphens (`dead-end`, `bubble`, `one-way`, `warp-sink`)
- Write failures must not break status refresh / provider seam
- `recommend_genesis` = genesis_candidates alias only (no new caller required)
- Explicit paths — never `git add -A`

## Accept

1. Dead-end sector gets `formation_membership` containing `dead-end` after scan
2. `catalog_world` and `WorldStats.refresh` both stamp membership
3. Focused tests green; live `n/a`

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_formations_catalog.py \
  tests/test_world_stats.py \
  -q
```
