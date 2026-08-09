# WO-CLEANUP-RUFF-F841-BANNER-FIRST-IDX

**Status:** DONE (pending merge)
**Priority:** LOW (WO-AI-TRANCHE-9 item 7, residual)
**Depends-on:** WO-CLEANUP-RUFF-F401-F841-BATCH (tip-closed on `origin/main` except this row)

## Goal

Remove the one remaining ruff F841 hit from the RUFF-F401-F841 batch/tranche
queue: a dead local assignment in
`tw2002_aiclient/session/classify.py`. Mechanical hygiene only — no behavior
change.

## Scope

- `tw2002_aiclient/session/classify.py:582` — remove the unused
  `banner_first_idx = min(...)` assignment in the TWGS game-select banner
  caller (the function computes `banner_last_idx` and uses only that).
- this WO file

## Out of scope

- `_twgs_banner_signals_coherent`'s own `banner_first_idx` (used at its
  proximity check, line 611) — **live**, not touched.
- Inventing a project linter / wiring ruff into CI.

## Accept

1. The dead `banner_first_idx` assignment at the caller is gone; the sibling
   live use inside `_twgs_banner_signals_coherent` is untouched.
2. `ruff check --select F401,F841 tw2002_aiclient/session/classify.py` clean.
3. Existing classify tests green (no new tests needed — no behavior change).
4. live-prove `n/a` (import/dead-assignment hygiene only).

## Proof

```bash
ruff check --select F401,F841 tw2002_aiclient/session/classify.py
.venv/bin/python -m pytest tests/test_classify.py -q
```
