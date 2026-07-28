# WO-TEST-INTERACTIVE-APP-REHAB — Archive interactive_app suite

**Status:** DONE · DELETE · Cursor (`impl-aiclient-cursor`)  
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

## Disposition (2026-07-28T16:43Z · Cursor)

**DELETE** (not rehab).

**Evidence:**
- Collect ERROR: `from twclient.control_lock import MODE_HUMAN` → `No module named 'twclient'`.
- Bootstrap drives `twclient.interactive_app.run_interactive_attach` / `AttachInputConn` (archive PTY attach).
- No live `tw2002_aiclient.interactive_app` module; reborn attach is cockpit/`tw attach` + `session` control_lock.
- Live pins: `tests/test_cockpit_attach.py`, `tests/test_attach_protocol.py`, `tests/test_control_lock.py`, CLI attach suite (`test_cli_attach_*`).
- Did **not** invent stubs.

Deleted `tests/test_interactive_app.py`; dropped `--ignore=tests/test_interactive_app.py` from `pytest.ini`.
