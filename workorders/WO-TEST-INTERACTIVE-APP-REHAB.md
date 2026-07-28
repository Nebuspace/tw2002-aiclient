# WO-TEST-INTERACTIVE-APP-REHAB — Archive interactive_app suite

**Status:** OPEN · EXECUTE · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28 · hub  
**Refs:** AUDIT-TEST-IGNORE-LIST-LANDMINE.md · `tests/test_interactive_app.py` still `--ignore`d (~243 lines)

## Goal
Assess **DELETE vs REHAB** for `tests/test_interactive_app.py`.

Likely **DELETE** if it is twclient/PTY archive with live overlap in cockpit attach / control_lock /
dead-terminal pins. Do **not** invent stubs.

## Accept
1. Disposition with evidence (imports · reborn twins · live pins).
2. If DELETE: remove file + drop `--ignore=tests/test_interactive_app.py`.
3. If REHAB: rewrite onto live product APIs only.
4. Suite green; live-prove `n/a`; pause for LIVE-PROVE HANDOFF.

## Out of bounds
No `test_spectate_app.py` (LARGE · separate). No product interactive redesign.
