# WO-WM-LANDMARKS-WRITE — populate landmarks from Ports line

**Status:** OPEN EXECUTE · HIGH · Claude Code preferred  
**Posted:** 2026-07-28T14:06Z · hub (CC 14:04:20Z evidence)  
**Amended:** 2026-07-28T15:19Z · CC PROCESS-NOTE constraints

## Goal

Teach `_ingest_settled_sector` / `sector_explore` writer to record `landmarks[]` from the settled screen’s `Ports :` line (e.g. StarDock). Today the screen carries StarDock but WM records `landmarks=[]`, so `find_landmark_sectors` never returns — starves GOALS stardock fields and stale `explore.py` caller claims.

## Constraints (load-bearing)

1. **OMIT `landmarks` when nothing was observed. Never write `[]`.** Upsert is field-replacing; unconditional `[]` erases a known StarDock on the next plain visit. Mirror `warps`/`port` tri-state in `_ingest_settled_sector` (and `world-model.md`: plain visit never clears landmarks).
2. **Canon tokens only:** `stardock`, `class_zero`, `own_planet`, `ferrengi` (lowercase snake). Spacing/underscores matter; `"Class Zero"` ≠ `class_zero`.
3. **Reuse existing `Ports :` parse** — `read_port_from_sector_status` already yields observed=True for StarDock lines; do **not** add a second row parser (`world-model.md` forbids).

## Accept

- Fixture screen with literal expected `landmarks` list (e.g. `["stardock"]`) — **not** “matching parse” as sole oracle (avoids both sides degrading together).
- Unobserved / warps-only settle: stored `landmarks` **unchanged** (key absent or prior value preserved — never wiped to `[]`).
- `find_landmark_sectors("stardock")` returns expected sectors in tests.
- No new per-draw WM scan; writer path only.

## Proof

- pytest; live-prove `n/a`

## Refs

- CC 14:04:20Z · 15:17:16Z PROCESS-NOTE · `WO-GOALS-STATUS-VOCABULARY` follow-on
