# WO-P2-OPS-VERB-HONESTY — README↔CLI verb-table honesty + SURFACE WO

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`a2c3afb`** (Cursor)
> Type: docs/inventory · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` (produced) · `canon/surfaces/spectate-and-attach.md`

## Goal
Close the banked README↔CLI gap: README advertised a full ops verb table; live `./tw --help` was `status`/`ensure` only. Inventory verbs in `session/cli.py` vs README; author `WO-P2-OPS-VERB-SURFACE.md` per-verb live/missing with execute slices; minimal README honesty patch (mark unimplemented or trim to shipped-only).

## Scope
- Inventory `tw2002_aiclient/session/cli.py` verbs vs README table
- Author `workorders/WO-P2-OPS-VERB-SURFACE.md`
- README minimal honesty patch (unimplemented verbs marked or trimmed)

## Constraints
- No verb implementation this WO (inventory + honesty only)
- No CC product paths

## Accept
1. `workorders/WO-P2-OPS-VERB-SURFACE.md` authored with per-verb live/missing status + ordered execute slices
2. README verb table honest (`./tw --help` still green; unimplemented marked)
3. No `AI-PILOT` in ops table

## Proof
`./tw --help` output cited; README lines changed cited. Hub verify Completeness 92 / Quality 93 → SHIP.

## Refs
hub Accept + Push GO @ 11:59:25Z · slice A–G ordered execute plan delivered
