# WO-TEST-SUITE-REHAB — Test suite rehab coordination (inventory → delete → rewrite wave)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · multi-commit wave
> Type: meta/coordination · Phase: 2 · Seat: impl-aiclient-cursor
> Child WOs: `WO-TEST-REHAB-INVENTORY.md` · `WO-TEST-REHAB-DELETE.md` · `WO-TEST-REHAB-REWRITE-LIVE.md` · `WO-TEST-REHAB-REWRITE-ENSURE.md` · `WO-TEST-COLLECT-HYGIENE.md`
> Refs: `tests/` · `pytest.ini`

## Goal
Coordinate the three-phase test-suite rehab wave:
1. Inventory: catalog live vs banked vs stale tests.
2. Delete: scoped delete of stale/dead tests.
3. Rewrite: greenfield rewrite of live pty / ensure / login harnesses off `twclient`.
4. Collection hygiene: align `pytest.ini` ignore list; verify clean collection.

## Outcome
Full wave complete. Suite collects cleanly. Banked tests remain carved out in `pytest.ini`.

## Refs
Inventory `WO-TEST-REHAB-INVENTORY.md` → Delete `WO-TEST-REHAB-DELETE.md` → Rewrite-live `WO-TEST-REHAB-REWRITE-LIVE.md` → Rewrite-ensure `WO-TEST-REHAB-REWRITE-ENSURE.md` → Hygiene `WO-TEST-COLLECT-HYGIENE.md`
