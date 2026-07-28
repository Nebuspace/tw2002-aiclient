# WO-TEST-SPECTATE-LAYOUT-REHAB — Archive spectate_layout suite

**Status:** OPEN · EXECUTE · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28 · hub  
**Refs:** AUDIT-TEST-IGNORE-LIST-LANDMINE.md · `tests/test_spectate_layout.py` still `--ignore`d

## Goal
Assess **DELETE vs REHAB** for `tests/test_spectate_layout.py`.

Likely **DELETE**: file imports `twclient.spectate_layout` (archive). Live coverage exists in
`tests/test_cockpit_spectate.py`, `tests/test_cockpit_layout.py`, mode-badge / no-send pins.
Do **not** invent a stub `spectate_layout` module.

## Accept
1. Disposition with evidence (twclient import sites · reborn product twins · live pins).
2. If DELETE: remove file + drop `--ignore=tests/test_spectate_layout.py` from `pytest.ini`.
3. If REHAB: rewrite onto live cockpit spectate/layout APIs only — no twclient.
4. Import-hygiene vacuity strings untouched unless they uniquely name this file and must update.
5. Suite green on changed paths; live-prove `n/a` (test hygiene).
6. Pause/CLAIM any hub `LIVE-PROVE` HANDOFF immediately.

## Out of bounds
No product spectate redesign. No `test_spectate_app.py` in this WO (separate LARGE).
