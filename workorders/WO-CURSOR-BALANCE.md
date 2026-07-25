# WO-CURSOR-BALANCE — Cursor seat workorders README + PREP balance while CC builds P2-020

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 (docs-only; SHA TBD — small docs tick)
> Type: docs · Priority: P2 · Seat: impl-aiclient-cursor
> Refs: `workorders/README.md` · hub HANDOFF @ 02:19:35Z

## Goal
Dual parallel while CC builds WO-P2-020: Cursor performs a brief workorders README balance pass + any small PREP docs task (keeping Cursor productive during CC's long 020 build wave). A: scanner dry-run fix + workorders/README update. B: path-leak confirmation.

## Scope
- `workorders/README.md` — minor balance update
- Coordination: path-leak scan dry-run A + B

## Outcome
Scanner dry-run: leak → exit 1 · clean → exit 0 ✅. P0-003…006 headers DONE + cited SHAs ✅. Lane-clean ✅.

## Refs
hub HANDOFF @ 02:19:35Z · ACK A∥B START @ 02:20:14Z · A REVISE + SHIP @ 02:23:18Z + 02:25:37Z
