# WO-TEST-COLLECT-HYGIENE — pytest collection hygiene: carve-outs, imports, INI alignment

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`92af7e2`** (Cursor; carve-out accepted)
> Type: hygiene · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `pytest.ini` · `tests/` collection

## Goal
Pytest collection hygiene: align `pytest.ini` ignore list after delete/rewrite wave; add explicit carve-outs for intentionally banked tests (attach redaction, login redaction — port deferred); verify full `pytest --collect-only` shows expected set.

## Scope
- `pytest.ini` — ignore list updated; carve-outs documented
- `tests/` — verify collection clean (no dead imports collected)

## Outcome
Hub ACCEPT-LIST [WO-TEST-COLLECT-HYGIENE · carve-out · 92af7e2] (carve-out accepted: some tests remain banked for future rehab).

## Refs
hub HANDOFF @ 04:22:50Z · hub ACCEPT-LIST @ 04:26:18Z SHA `92af7e2`
