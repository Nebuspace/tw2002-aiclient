# WO-OPEN-003-DOCS — OPEN-003 docs: update canon + README for host:port resolver

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`3e2316a`** (Cursor; pushed)
> Type: docs · Phase: 0 · Seat: impl-aiclient-cursor
> Refs: `WO-OPEN-003-A.md` (implementation) · `WO-OPEN-003-DECISIONS-CLOSE.md` (formal close) · `WO-OPEN-003-host-port-resolver.md`

## Goal
Update canon docs and README to reflect the OPEN-003 host:port resolver contract (TW_CONFIG_DIR, `credentials.py`, resolved host/port fields). The code implementation WO is `WO-OPEN-003-A.md`; this WO covers the documentation side.

## Scope
- `canon/` — update any concept that mentions host/port resolution or credentials path
- `README.md` (repo root) — update TW_CONFIG_DIR / credentials usage section

## Accept
- Canon correctly describes the resolver contract as shipped
- README updated for new TW_CONFIG_DIR usage
- SHA `3e2316a` on origin

## Refs
hub HANDOFF @ 04:48:44Z · hub ACCEPT `3e2316a` @ 04:49:39Z · CLOSED @ 04:50:13Z · Cursor STATUS DONE @ 04:49:19Z
