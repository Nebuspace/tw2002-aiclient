# WO-TEST-AICLIENT-ADAPTERS-REHAB — Rehab or DELETE ignored adapters tests

**Status:** DONE · DELETE · Cursor (`impl-aiclient-cursor`)  
**Posted:** banked #149 · EXEC after #153  
**Refs:** AUDIT — STALE_API `_launcher_selectable` on test_aiclient_adapters.py

## Goal
Honest disposition for ignored `tests/test_aiclient_adapters.py` (and siblings named in audit
if in-scope): rehab onto in-tree APIs **or** DELETE if producer symbols are gone. No stubs.

## Accept
1. Evidence-based rehab+un-ignore or DELETE+drop ignore.
2. Leave import-hygiene vacuity pins untouched.
3. Suite green; live-prove n/a.

## Constraints
Cite audit. Avoid #147 cockpit/chains. Explicit paths. No twclient resurrect.

## Disposition (2026-07-28)

**DELETE.** Ignored suite targeted dead product surface:
- `adapters.resolve_run_dir` / `default_run_dir_for_profile` / `ensure_and_sync_autopilot` /
  `toggle_autopilot_and_sync` / `list_launcher_rows` — not on live `adapters.py`
  (live adapters = ensure/explore/autoloop; run-dir lives in `session/env.py`).
- `screens._launcher_selectable` / `_launcher_step` — gone.
- Function-level `import twclient.cli` — #142 landmine class.

Live coverage remains: `tests/test_adapters_*.py`, `tests/test_cli_run_dir*.py`.
Import-hygiene vacuity pins untouched.
