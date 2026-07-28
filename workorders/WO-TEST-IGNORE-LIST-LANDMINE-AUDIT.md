# WO-TEST-IGNORE-LIST-LANDMINE-AUDIT — What the 39 ignored tests hide

**Status:** OPEN · EXECUTE · HIGH · Cursor (`impl-aiclient-cursor`) OK; CC OK  
**Posted:** 2026-07-28T04:26Z overnight · after formations landmine + CC correction  
**Refs:** pytest.ini --ignore list · CC 04:16:48Z (37/39 hard-fail on twclient) · wire plan

## Goal
Audit every `--ignore`d test file: mechanism of failure (twclient import vs other),
reachability of product code it *would* cover, and disposition (rehab / delete / keep-ignored
with honest reason). Landmine class: ignored tests that hide armed product bugs.

## Accept
1. Table of all ignored files with: import-collect result (bypassing ignore), failure class,
   product surfaces implicated, recommended disposition.
2. At least **bank** follow-on WOs for any HIGH landmine-class rows (armed product + ignored
   only coverage) — do not silently widen this WO into full rehab of all 39.
3. Optional: one small rehab/delete if trivially safe and disjoint from #147.
4. STATUS + suite green on any product touch. live-prove n/a.

## Constraints
Do not mass-unignore without rehab. No new deps. Explicit paths. Avoid `cockpit/chains` /
CHAINS-TUI (#147 CC) collision. Public-repo safe.
