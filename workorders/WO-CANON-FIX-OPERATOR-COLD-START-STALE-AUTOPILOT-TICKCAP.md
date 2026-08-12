# WO-CANON-FIX-OPERATOR-COLD-START-STALE-AUTOPILOT-TICKCAP

**Status:** IN FLIGHT (impl-aiclient-h1 · audit-refill batch)

## Goal

Replace the Live seat recovery table's dead pre-rebirth Autopilot tick-cap row
(`ticks_done==500`, `max_ticks_exhausted`) with tip-true intervention signatures.

## Scope

- `canon/surfaces/operator-cold-start.md` — recovery table + tip-honesty note
- This WO (shipped in PR with sibling citation WOs)

## Accept

Table no longer cites `ticks_done` / `max_ticks_exhausted`; documents
`status.autopilot={running:bool}` and `intervention` reason codes
(`explore_exhausted`, game-select / `autopilot_game_select`, `warp_confirm`).

## Proof

Docs-only · live-prove **n/a**
