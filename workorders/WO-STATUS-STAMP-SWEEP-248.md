# WO-STATUS-STAMP-SWEEP-248 — stamp shipped Play/autoloop WOs DONE

**Status:** OPEN · EXECUTE · LOW · queue honesty · Cursor-only  
**Posted / seeded:** 2026-07-30T08:27Z · hub (post-#248; DECISIONS overlay tranche closed)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `70cffa6`  
**Refs:** merged PRs #237–#248 · workorders still saying OPEN/EXECUTE

## Goal

Stamp **Status: DONE** (with merge tip / PR) on workorder files that already
shipped on `main` but still read OPEN · EXECUTE — so IDLE-KICK / queue scans
stop treating finished work as live.

## Scope (exact list — do not invent more)

Update **only** these files' Status line (and a one-line Done tip if the
template already has one):

| WO file | Merged as |
|---|---|
| `WO-PLAY-RULE-IDENTITY.md` | #237 |
| `WO-PLAY-RULES-LIBRARY.md` | #238 |
| `WO-PLAY-RULE-SCOPE.md` | #239 |
| `WO-PLAY-RULES-SHOW-SCOPE.md` | #240 |
| `WO-AUTOLOOP-TURN-BUDGET.md` | #241 |
| `WO-AUTOLOOP-HAZARD-HALT.md` | #242 |
| `WO-AUTOLOOP-CYCLES.md` | #243 |
| `WO-AUTOLOOP-CYCLE-PROGRESS.md` | #244 |
| `WO-WIRE-EXPLORE-DECISION-LINES.md` | #245 |
| `WO-EXPLORE-DECISION-FLAGS.md` | #246 |
| `WO-RETIRE-CYCLE-EXPLORE-MODE.md` | #247 |
| `WO-EXPLORE-DECISION-TURNS.md` | #248 |

Resolve each PR's merge commit SHA from `gh pr view N --json mergeCommit`
(or `git log --grep` on main). Status shape e.g.:

`**Status:** DONE · origin \`<sha7>\` (#N) · Accept verified <date>`

## Constraints

- Docs-only under `workorders/`. No product code.
- Explicit paths only. No other WO files.
- Suite green (docs-only still runs). Live prove: `n/a`.

## Accept

1. All twelve files stamped DONE with correct PR + tip SHA.
2. No other files touched.
3. Suite green · live `n/a`.

## Proof

```bash
# Status lines no longer OPEN for the twelve
rg -n "^\\*\\*Status:\\*\\*" workorders/WO-{PLAY-RULE,AUTOLOOP,WIRE-EXPLORE,EXPLORE-DECISION,RETIRE-CYCLE}*
pytest -q tests  # or suite CI
```
