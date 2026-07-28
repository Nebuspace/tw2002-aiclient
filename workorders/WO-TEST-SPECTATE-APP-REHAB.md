# WO-TEST-SPECTATE-APP-REHAB — Archive spectate_app mega-suite

**Status:** OPEN · EXECUTE · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28 · hub  
**Refs:** AUDIT-TEST-IGNORE-LIST-LANDMINE.md · `tests/test_spectate_app.py` still `--ignore`d (~2663 lines · LARGE)

## Goal
Assess **DELETE vs REHAB** for `tests/test_spectate_app.py`.

Likely **DELETE**: archive twclient spectate app; live coverage in cockpit spectate / no-send / layout pins.
Do **not** invent stubs. Prefer DELETE over partial port of a mega-suite.

## Accept
1. Disposition with evidence.
2. If DELETE: remove file + drop `--ignore=tests/test_spectate_app.py`.
3. Suite green; live-prove `n/a`; pause for LIVE-PROVE.

## Out of bounds
No product spectate redesign. Remaining KEEP ignores (haggle/crawl/ledger/analyze/trade_driver) stay out of scope.
