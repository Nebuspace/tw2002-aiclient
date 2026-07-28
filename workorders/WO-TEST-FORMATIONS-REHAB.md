# WO-TEST-FORMATIONS-REHAB — Rewrite formations tests off twclient

**Status:** BANKED · HIGH · Cursor-class OK  
**Posted:** 2026-07-28T04:32Z · from #149 ignore-list audit  
**Refs:** `tests/test_formations.py` ignored · #142 product disarm · `explore.plan_find_formations`

## Goal
Rehabilitate formations coverage onto reborn `tw2002_aiclient.explore` (catalog
seam / `unavailable` honesty). Un-ignore only after collect+suite green.

## Accept
1. No `twclient` import in the formations test module.
2. Pins cover `catalog_provider is None` → `unavailable` and provider-present paths as product defines.
3. Remove `--ignore=tests/test_formations.py` when green.
4. Suite + STATUS. live-prove n/a.

## Constraints
Do not resurrect `twclient.formations`. No CHAINS-TUI collision.
