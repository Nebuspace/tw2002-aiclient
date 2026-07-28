# WO-TEST-SPECTATE-LAYOUT-REHAB — Archive spectate_layout suite

**Status:** DONE · DELETE · Cursor (`impl-aiclient-cursor`)  
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

## Disposition (2026-07-28T16:37Z · Cursor)

**DELETE** (not rehab).

**Evidence:**
- Module import: `from twclient.spectate_layout import …` → `ModuleNotFoundError: No module named 'twclient'` on collect.
- Additional in-file `twclient` imports: `chains`, `priority_engine`, `menu_map_view`, `formations`, `coach_kb` (archive AI-pilot / spectate stack).
- No live `tw2002_aiclient.spectate_layout` module; archive source only under `archive/…/twclient/spectate_layout.py`.
- Reborn twins / pins: `tests/test_cockpit_layout.py`, `tests/test_cockpit_spectate.py`, `tests/test_spectate_no_send.py`, plus `tests/test_mode_badge_vocabulary.py` (mode-badge).
- Did **not** invent a stub `spectate_layout`.

Deleted `tests/test_spectate_layout.py`; dropped `--ignore=tests/test_spectate_layout.py` from `pytest.ini`.
