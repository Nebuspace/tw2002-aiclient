# WO-TEST-AICLIENT-ADAPTERS-REHAB — Rehab or DELETE ignored adapters tests

**Status:** OPEN · EXECUTE · HIGH · Cursor (`impl-aiclient-cursor`)  
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
