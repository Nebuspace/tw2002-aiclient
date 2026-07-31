# WO-STATUS-STAMP-SWEEP-250 — stamp remaining shipped-but-OPEN WOs

**Status:** DONE · origin `9e6601e` (#251) · tip-honesty stamp 2026-07-31 (product on main; banner was stale OPEN)
**Posted / seeded:** 2026-07-30T12:53Z · hub  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `abaf47c`  
**Refs:** #249 stamp pattern · Max Play-visible bias (hygiene only when it unblocks queue truth)

## Goal

Several WOs shipped on `main` still say **OPEN**. Flip their Status lines to DONE with the verified merge tip SHA + PR number (same format as #249).

## Exact stamp set

Verify each via `gh pr view <N> --json mergeCommit -q .mergeCommit.oid` (do not trust table tip if gh disagrees):

| WO file | PR |
|---|---|
| `workorders/WO-ENSURE-STALE-SOCK-RECOVER.md` | #210 |
| `workorders/WO-ADAPTERS-FIGHT-TOLLS.md` | #211 (if present; else stamp dock-dialect sibling that #211 closed) |
| `workorders/WO-EXPLORE-DOCK-DIALECT.md` | #211 |
| `workorders/WO-PLAY-EXPLORE-FLAGS.md` | #212 |
| `workorders/WO-EXPLORE-HALT-REASON-CLASS.md` | #213 |
| `workorders/WO-TEST-CI-SKIP-COUNT-GUARD.md` | #234 |
| `workorders/WO-PLAY-REFLEX-ARM.md` | #235 |
| `workorders/WO-PLAY-REFLEX-AFFORDANCE.md` | #236 |

Format: `**Status:** DONE · origin \`<sha7>\` (#N) · Accept verified 2026-07-30`

Skip any file already DONE. If a listed WO was never merged, leave OPEN and report in STATUS (do not invent).

## Accept

1. Listed OPEN files that shipped → DONE with correct PR+SHA.  
2. Docs-only (workorders Status lines). No product code.  
3. Suite green · live `n/a`.

## Proof

```bash
# no OPEN among successfully stamped files; gh mergeCommit matches Status SHA
pytest -q -n auto   # or suite CI on the PR tip
```
