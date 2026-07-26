# WO-FIND-MENU-PATH-KIND-FILTER-SCOUT

**Status:** DONE · scout complete 2026-07-26 (CC @ 01:43:14Z) · no product change  
**Posted:** 2026-07-25T20:04:13Z

## Goal

Design scout only — `find_menu_path` BFS has no kind filter while canon says safe-kinds-only; empirically not live today (action→sentinel). Propose filter-at-BFS vs gate-at-execution; **no product change** this WO.

## Outcome (CC 01:43 / restated 04:59)

Safety today is **emergent**: nothing writes `from_node=<unexplored>` (0 sites in `crawler.py`). Router has no opinion. Becomes live if crawler presses recorded-not-pressed options, hand-edited store, or second writer.

**Recommendation (not built):** kind filter in BFS (structural) vs gate-at-execution — design call for router WO. Cheapest interim: one-line assert at `find_menu_path` naming the invariant (separate tiny WO if wanted).

## Accept

Met — scout STATUS recorded; no product tip.

## Refs

CC 2026-07-26T01:43:14Z · 04:59:29Z · MENU_EDGE_KINDS
