# WO-P2-WATCHHUB-PORT — WatchHub settle-edge push-stream substrate

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`1825758`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` WATCHHUB · `canon/surfaces/spectate-and-attach.md` N2

## Goal
Port greenfield `WatchHub` settle-edge push-stream so `tw watch` / spectate can wire later without inventing fake verbs. New `tw2002_aiclient/session/watch.py` + daemon `subscribe` lifetime. Subscribers are read-only; must not take control_lock / send game input.

## Scope
- `tw2002_aiclient/session/watch.py` — `WatchHub` class
- `tw2002_aiclient/session/daemon.py` — hub start/stop + `_handle_subscribe` protocol
- `tests/test_watch*.py` (FakeSession) — ≥1 prove settle-edge event delivery
- `README.md` / `WO-P2-OPS-VERB-SURFACE.md` — note substrate landed
- Path-leak

## Constraints
- Subscribers read-only: must not take control_lock / send game input
- No CLI `watch` verb yet (honest); E2 follows
- Prefer archive `watch.py` (~113 LOC) as shape reference; do not duplicate settle logic

## Accept
1. `WatchHub` importable
2. Daemon exposes subscribe stream
3. ≥1 FakeSession/protocol test proves settle-edge event delivery
4. No CLI `watch` verb yet (honest)

## Proof
Targeted watch tests + full suite. Hub Completeness 95 / Quality 94 / Safety 96 / Craft 93 → SHIP.

## Refs
`WO-P2-OPS-VERB-SURFACE.md` WATCHHUB · `spectate-and-attach.md` N2 · hub Accept + Push GO @ 14:26:45Z
