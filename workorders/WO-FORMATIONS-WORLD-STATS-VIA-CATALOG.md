# WO-FORMATIONS-WORLD-STATS-VIA-CATALOG — One detector for panel + explore

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct, hub authorized continuous self-direct)  
**Posted:** 2026-08-03T00:08:43Z  
**Branch:** `wo/FORMATIONS-WORLD-STATS-VIA-CATALOG`  
**Zone:** `tw2002-aiclient` only  
**Refs:** #317 `formations.catalog_world` · `world_stats._refresh_dead_ends` · `canon/strategy/special-formations.md`

## Goal

Eliminate the dual one-warp scanners: `WorldStats` must feed `dead_end_count` /
`formations_*` / `formations_panel` from the same detector explore uses
(`formations`), without changing dead-end-only product scope or the
leave-prior-on-hostile-store semantics.

## Verify-first

`world_stats._refresh_dead_ends` reimplements the length-1 warp loop already in
`catalog_world`. Drift risk: panel/GOALS/coach can disagree with
`plan_find_formations` / explore. Also: `catalog_world` maps store failures to
an empty catalogue; `WorldStats` correctly leaves the prior observation
untouched — unification must keep that distinction.

## Scope

- `tw2002_aiclient/formations.py` — extract `formations_from_sectors` (abort →
  `None`; valid empty → empty catalog); `catalog_world` calls it
- `tw2002_aiclient/world_stats.py` — `_refresh_dead_ends` uses shared detector
- `tests/` — pin shared path + hostile mid-list leave-prior for WorldStats
- `workorders/WO-FORMATIONS-WORLD-STATS-VIA-CATALOG.md` — this file

## Constraints

- Dead-end-only detector unchanged (bubbles / one-ways / warp-sinks = later WO)
- Do **not** widen Play E-cycle / `ARMABLE_INTENTS` (#247)
- Panel item display (`Dead-end #{sid}` / existing blurb) stays behavior-neutral
- Explicit paths — never `git add -A`

## Accept

1. One pure detector over a sectors list; both `catalog_world` and `WorldStats` call it
2. `WorldStats` still leaves prior observation untouched when `all_sectors` raises
   or returns a hostile mid-list (non-dict record)
3. Provider seam still never raises (`catalog_world` maps abort → empty catalog)
4. Focused tests green; live `n/a` (offline detector unify, no live path change)

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_formations_catalog.py \
  tests/test_world_stats.py \
  -q
```
