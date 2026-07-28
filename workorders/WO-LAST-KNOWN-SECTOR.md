# WO-LAST-KNOWN-SECTOR — daemon remembers last successfully-read sector

**Status:** DONE · origin `e54b975` (#169) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28T15:30Z · hub (CC #165 DECISION 15:27Z)

## Goal

Remember the last successfully-read sector id in the single-connection daemon so sector-less-but-classified screens (StarDock menu / shipyard fixtures) can attribute landmarks / other per-sector writes.

## Why

StarDock screens classify correctly but carry **no `[sector]`** in the Command prompt; `read_current_sector` → absent; explore `_gate_screen` → unrecognized (halts). No `last_sector` memory exists today (`protocol.py` re-reads per prompt).


## Staleness (hub-ruled 2026-07-28T15:44Z)

**(b) monotonic move-counter** — bump on every send that could change sector; attribute landmarks only when counter is unchanged since the last successful sector read. Invalidation-by-remembered-rule (a) and "no intervening send" (c) are insufficient under a threaded daemon.

## Accept

1. Daemon exposes last-known sector + move-counter (updated only on successful sector reads; absent until first success; attribute only when counter unchanged since that read).
2. Client/write path can attribute landmark upsert when current screen is sector-less but StarDock-classified.
3. Pins: never invent a sector; clear/reset rules on disconnect; suite + Cipher glance on threaded daemon state.
4. live-prove: **DEFERRED → Cursor** (Max 2026-07-28) — CC does not run live; hub LIVE-PROVE-HANDOFFs Cursor after suite green. Docs/offline cells may still n/a with reason.

## Out of scope

- Ports-name flyby extractor (still banked until live capture)
- Widening `write_from_state` to landmarks

## Refs

- CC 15:27:05Z · `WO-WM-LANDMARKS-WRITE` P2 · classify `stardock_*` fixtures
