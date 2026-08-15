# WO-AICLIENT-CLEANUP-CELL-AT-UNUSED-HELPER

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1

## Goal

Delete unused `cell_at()` in `tests/pty_helpers.py` (zero callers).

## Changes

- Removed `cell_at`; callers already use `screen.buffer[row][col]` /
  `pyte_screen` docs directly.

## Accept

- [x] `cell_at` gone; `rg cell_at tests/ tw2002_aiclient/` → 0 (except
      historical workorder prose)
- live-prove: **n/a** (test harness only)

## Proof

```bash
rg -n 'def cell_at|cell_at\(' tests/pty_helpers.py   # expect 0
.venv/bin/python -m pytest tests/test_pty_helpers_smoke.py -q -n0
```
