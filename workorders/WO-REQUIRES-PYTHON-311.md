# WO-REQUIRES-PYTHON-311 — Align declared Python floor with reality

**Status:** SEAT-DONE · awaiting hub Accept · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28T04:20Z · hub ruling overnight (CC DECISION-NEEDED) · seat STATUS 2026-07-28T04:26Z  
**Refs:** CC 04:16:48Z · `pyproject.toml` requires-python · tomllib/tomli gap

## Hub ruling
**(b)** Raise `requires-python` to `>=3.11`. Do **not** add `tomli`.
Declared 3.10 support was a lie: credentials/protocol fall back to missing `tomli`.

## Accept
1. `pyproject.toml` `requires-python = ">=3.11"` (+ any mirrored CI/docs claiming 3.10).
2. Optional: delete dead `tomli` ImportError fallbacks + pin `tomllib` imports, or leave fallbacks.
3. Suite + STATUS. live-prove n/a.

## Constraints
No new dependencies. Explicit paths. Do not touch CHAINS-TUI (#147 CC).
