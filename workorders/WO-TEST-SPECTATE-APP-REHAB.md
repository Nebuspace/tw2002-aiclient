# WO-TEST-SPECTATE-APP-REHAB — Archive spectate_app mega-suite

**Status:** DONE · DELETE · Cursor (`impl-aiclient-cursor`)  
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

## Disposition (2026-07-28T16:49Z · Cursor)

**DELETE** (not rehab) — prefer DELETE over partial port of mega-suite.

**Evidence:**
- Collect ERROR: `from twclient import chains, terminal` → `No module named 'twclient'`.
- Imports archive `twclient.spectate_app` / `spectate_layout` / `world_model` / `game_knowledge` / `menu_sig` (~2663 lines).
- No live `tw2002_aiclient.spectate_app` (deleted at rebirth; kernels ported into cockpit tones/liveness/viewport_color/layout).
- Live pins: `tests/test_cockpit_spectate.py`, `tests/test_spectate_no_send.py`, `tests/test_cockpit_layout.py` (+ sibling cockpit PTY/layout suites).
- Did **not** invent stubs.

Deleted `tests/test_spectate_app.py`; dropped `--ignore=tests/test_spectate_app.py` from `pytest.ini`.
