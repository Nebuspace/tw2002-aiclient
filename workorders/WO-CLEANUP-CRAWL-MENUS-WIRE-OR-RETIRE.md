# WO-CLEANUP-CRAWL-MENUS-WIRE-OR-RETIRE

**Priority:** MED  
**Disposition:** PARK / SUPERSEDE → `WO-GATED-MENU-CRAWL-DRIVER-REBUILD`  
**Claimed-by:** impl-aiclient-h1

## Goal

Cleanup-removal lens flagged `crawl_menus()` as zero product callers. Tip-check shows this
overlaps the already-gated live-driver rebuild question — not a safe ungated WIRE, and not a
safe RETIRE of the never-commit suite.

## Decision (this WO)

**Neither wire nor retire.** Tip-honest park:

1. File missing `canon/DECISIONS.md#PENDING-MENU-CRAWL-LIVE-DRIVER-REBUILD` (queue already cited it).
2. Mark library as intentionally parked in crawler docstring + cli-verbs + menu-map + action-safety-guards.
3. Leave Max-gated rebuild as the only path to product invocation.

## Accept

- [x] DECISIONS Pending exists and matches queue cite
- [x] Canon no longer frames `crawl_menus` as orphan-dead
- [x] Never-commit tests untouched
- live-prove: n/a (docs/decision park)

## Out of scope

- Restoring `crawl_driver` / `tw crawl` / `crawl_start` (gated)
- Deleting `tests/test_menu_crawler.py` or chokepoint suite
