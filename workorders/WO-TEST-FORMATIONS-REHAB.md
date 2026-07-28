# WO-TEST-FORMATIONS-REHAB — Rehabilitate tests/test_formations.py onto tw2002_aiclient

**Status:** OPEN · EXECUTE · HIGH · Cursor (`impl-aiclient-cursor`)  
**Posted:** banked #149 · EXEC overnight after Accept  
**Refs:** ignore-list audit HIGH · #142 catalog_provider / unavailable seam

## Goal
Rewrite/un-ignore `tests/test_formations.py` onto in-tree APIs (`catalog_provider` seam /
`plan_find_formations` unavailable honesty). No `twclient`.

## Accept
1. Remove `--ignore=tests/test_formations.py` once tests collect+pass.
2. Pins cover refuse/unavailable path and post-#142 routing coverage where applicable.
3. Suite green; live-prove n/a.

## Constraints
Do not resurrect twclient. Avoid #147 cockpit/chains product edits. Explicit paths.
