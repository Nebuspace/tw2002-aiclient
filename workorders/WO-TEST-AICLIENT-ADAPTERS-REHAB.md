# WO-TEST-AICLIENT-ADAPTERS-REHAB — Fix or delete stale adapters test

**Status:** BANKED · MED→HIGH · Cursor-class OK  
**Posted:** 2026-07-28T04:32Z · from #149 ignore-list audit  
**Refs:** `tests/test_aiclient_adapters.py` · missing `screens._launcher_selectable`

## Goal
`test_aiclient_adapters.py` imports reborn `tw2002_aiclient` but fails collect on a
deleted symbol (and still pulls `twclient`). Rehab onto current adapters/screens
surface **or** delete with a note that live adapter tests supersede.

## Accept
1. File either green+collected or removed with `--ignore` line gone.
2. No `twclient` dependency left if kept.
3. Suite + STATUS. live-prove n/a.

## Constraints
No inventing `_launcher_selectable`. Explicit paths.
