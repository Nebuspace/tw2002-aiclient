# WO-TEST-REHAB-DELETE — Delete stale/dead test files (twclient imports, archive stubs)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tips **`915e4d8`** + **`ce3e523`** (Cursor)
> Type: cleanup · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-TEST-REHAB-INVENTORY.md` inventory · `pytest.ini` · `WO-TEST-SUITE-REHAB.md`

## Goal
Delete stale test files identified in the inventory: tests that import `twclient` with no path to greenfield port, dead archive references, test stubs with no assertions. Scoped delete — do not delete banked tests with future value.

## Scope
- `tests/**/*.py` — delete set per inventory (stale/dead only)
- `pytest.ini` — un-ignore entries for deleted files

## Outcome
Hub ACCEPT [WO-TEST-REHAB-DELETE · SHIP · 915e4d8 + ce3e523].

## Refs
hub HANDOFF @ 03:51:26Z · hub ACCEPT @ 03:52:56Z tips `915e4d8` + `ce3e523`
