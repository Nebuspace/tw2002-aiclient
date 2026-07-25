# WO-P2-OPS-VERB-E2 — tw watch CLI (NDJSON/settle-edge tail over daemon subscribe)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`b9dc80d`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice E2 · `canon/surfaces/spectate-and-attach.md`

## Goal
Wire `tw watch` CLI as NDJSON/settle-edge tail over live daemon `subscribe` (substrate from WATCHHUB-PORT on tip). Ctrl-C / `--frames N` closes the socket cleanly without driving the game.

## Scope
- `tw2002_aiclient/session/cli.py` (`tw watch` sub-command)
- Optional thin protocol client helper under session/
- `tests/` — FakeSession/protocol proof of ≥1 settle-edge event printed
- `_SHIPPED_VERBS` allowlist + README
- `WO-P2-OPS-VERB-SURFACE.md` E2 tick

## Constraints
- Subscribers stay read-only (no control_lock; no game sends)
- Ctrl-C / disconnect cleans up without crash
- Honest: no second WatchHub invented; uses substrate from WATCHHUB-PORT
- Full suite green

## Accept
1. `tw watch` on `./tw --help`
2. FakeSession/protocol proof of ≥1 settle-edge event printed as NDJSON
3. `--frames N` closes after N events; Ctrl-C clean
4. Allowlist + README updated

## Proof
Targeted + full suite. Hub Completeness 96 / Quality 95 / Safety 96 / Craft 94 → SHIP.

## Refs
`WO-P2-OPS-VERB-SURFACE.md` E2 · archive `cmd_watch` NDJSON shape · hub Accept + Push GO @ 14:32:01Z
