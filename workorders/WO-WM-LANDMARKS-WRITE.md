# WO-WM-LANDMARKS-WRITE — populate landmarks from Ports line

**Status:** BANKED · HIGH  
**Posted:** 2026-07-28T14:06Z · hub (CC 14:04:20Z evidence)

## Goal

Teach `_ingest_settled_sector` / `sector_explore` writer to record `landmarks[]` from the settled screen’s `Ports :` line (e.g. StarDock). Today the screen carries StarDock but WM records `landmarks=[]`, so `find_landmark_sectors` never returns — starves GOALS stardock fields and stale `explore.py` caller claims.

## Accept

- After explore settle on a sector with StarDock (or other landmarks) on screen, WM record has non-empty `landmarks` matching parse.
- `find_landmark_sectors("StarDock")` returns expected sectors in tests with FakeTWGS/fixture screen.
- No new per-draw WM scan; writer path only.

## Proof

- pytest; live-prove `n/a`

## Refs

- CC 14:04:20Z · `WO-GOALS-STATUS-VOCABULARY` follow-on
