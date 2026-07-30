# WO-LANDMARK-ATTRIBUTE-LAST-KNOWN — attribute landmarks via last_known_sector

**Status:** DONE · product `_attribute_landmark` on main (post #169) · Accept verified 2026-07-30 · stamp with WO-GOALS-STARDOCK-STATUS  

**Posted:** 2026-07-28T16:28Z · hub (CC honesty HEADS-UP 16:22:50Z)

## Goal

Wire a product consumer of `Session.last_known_sector()` so sector-less StarDock-classified screens can attribute `landmarks` via `upsert_sector` when memory is present — and **refuse** (no write) when it returns `None`.

## Why

#169 ships the memory + epoch safety with **zero product readers** (only tests). Inverse of starved `chain_hops` (consumer without producer). Without this WO the memory sits unused.

## Accept

1. At least one product call site attributes landmark only when `last_known_sector()` is non-None.
2. Pin: `None` → no upsert / no wrong-sector write.
3. Suite + LIVE-PROVE DEFERRED → Cursor (or n/a if offline-only proveable).

## Depends

- #169 merged (`last_known_sector` / epoch on main)

## Refs

- CC 16:22:50Z · `WO-LAST-KNOWN-SECTOR` · `WO-WM-LANDMARKS-WRITE` P1
