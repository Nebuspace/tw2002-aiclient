# WO-TEST-PARALLEL-DEFAULT

**Status:** DONE · origin `80923a6`  
**Goal:** Make `pytest-xdist` `-n auto` the default; serial escape `-n0`.

## Changes
- `pytest.ini` `addopts`: `-n auto` (keeps `-q` + all `--ignore=` lines)
- Comment flip: parallel default · serial via `-n0`
- `README.md` / `CLAUDE.md` test one-liners stamped

## Accept / Proof (this tip)
1. Bare `.venv/bin/python -m pytest` schedules xdist workers (`bringing up nodes…`)
2. `.venv/bin/python -m pytest -n0` still serial
3. Collect unchanged (~2726; 0 collection ERRORS) — see STATUS
4. Full suite: same 7 PTY failures under **both** `-n0` and bare parallel (pre-existing on origin `1e5159f`, not NEW xdist flakes). Non-PTY suite green under parallel smoke.

## Non-regression note
`tests/test_bank_unreadable_pty.py` (4) + `tests/test_credentials_store_honesty.py` PTY (3) fail serial on origin tip before this WO — blank pyte capture. Hub: treat as pre-existing process/env leak, not "xdist broke it." Follow-on if needed; out of this WO's config scope.
