# WO-TEST-WORLD-MODEL-INTEGRATION-REHAB — rehab or DELETE ignored world_model integration suite

**Status:** OPEN EXECUTE · MED · Cursor preferred  
**Posted:** 2026-07-28T16:01Z · hub (#149 AUDIT BANK-REHAB MED · BANK-DELETE queue drained)

## Goal

Honest disposition for ignored `tests/test_world_model_integration.py` (twclient-era). Product `world_model` is live (#164/#165/#166). Either **rehab** onto in-tree APIs + un-ignore, or **DELETE** if the archive suite only covers deleted APIs and live pins already supersede (`test_world_model*.py` / landmarks / known_sector_count).

## Accept

1. Evidence-based rehab+un-ignore **or** DELETE+drop `--ignore=tests/test_world_model_integration.py`.
2. Do not invent stubs. Leave import-hygiene vacuity untouched.
3. Suite green; live-prove `n/a`. Pause for LIVE-PROVE #169 if hub posts.

## Out of bounds

- CC #169 product paths · KEEP-IGNORED haggle/crawl/trade_driver rows

## Refs

- `AUDIT-TEST-IGNORE-LIST-LANDMINE.md` · live `world_model.py`
