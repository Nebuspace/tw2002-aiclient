# WO-CLEANUP-RUFF-F401-F841-BATCH

**Status:** DONE · PR #528 · unused-import batch on tip  
**Priority:** LOW (Cycle-34 / Cycle-43 queue · ungated)  
**Depends-on:** none

## Goal

Remove verified-unused imports (ruff F401 class) that the unused-code /
Cycle-34 batch flagged. Mechanical hygiene only — no behavior change.

## Scope

- `tw2002_aiclient/cockpit/chains.py` — drop unused `Any`
- `tw2002_aiclient/cockpit/draft_approve.py` — drop unused `Optional`
- `tw2002_aiclient/ledger.py` — drop unused `Optional`
- `tw2002_aiclient/session/sector_explore.py` — drop unused `map_fill_warp_target`
- `tw2002_aiclient/loops/player.py` — drop unused `QUALIFIER_SEP`
- `tw2002_aiclient/screens.py` — drop unused `credentials` import
- this WO file

## Out of scope

- `session/classify.py` `banner_first_idx` — **live** (used in proximity check); do not remove
- Inventing a project linter / wiring ruff into CI

## Accept

1. Named unused imports gone; no other symbol churn.
2. Related import/unit tests green.
3. live-prove `n/a` (import hygiene only).

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_cockpit_chains.py tests/test_ledger.py \
  tests/test_sector_explore.py -q -n0
```
