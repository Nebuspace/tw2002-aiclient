# WO-80x25-WORKORDERS-SWEEP — Workorders 80×24→80×25/82×27 viewport size sweep (docs-only)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-25 · tip **`0ea5e74`** (Cursor; pushed)
> Type: docs/workorders · Phase: 4 · Seat: impl-aiclient-cursor
> Refs: `workorders/WO-P4-050-057-viewport-PREP.md` · `workorders/WO-11-game-viewport-center.md` · `workorders/README.md` · `workorders/ULTRACODE-WO-INVENTORY.md`

## Goal
Sweep workorder docs for stale 80×24 game viewport size references and update to 80×25 / 82×27 (bordered) as appropriate after PWO-051 grew to 80×25 in `bb780e0`. Three-class classification:

**(a) Update — stale GAME viewport size:**
- `workorders/WO-P4-050-057-viewport-PREP.md` Accept/Proof lines still saying "80×24 interior budget"
- `workorders/WO-11-game-viewport-center.md` GAME grid / bordered viewport claims
- `workorders/README.md` native game viewport line
- `workorders/ULTRACODE-WO-INVENTORY.md` center viewport shell row title / bordered dims

**(b) Do NOT touch — minimum terminal size ≥80×24 (different referent):**
- `WO-10-cockpit-outer-frame.md` · `WO-P3-030-033-cockpit-frame-PREP.md` · `ULTRACODE-WO-INVENTORY.md` overlap ≥80×24 rows · `WO-06-live-panels-poll.md`

**(c) History — leave or annotate, do not rewrite as if always 25:**
- PREP DONE narrative for PWO-051 "80×24 interior budget" — annotated as grown in `bb780e0`, not rewritten

## Scope
- `workorders/` docs only — no product code, no canon/
- Dual-spelling classification (80×24 terminal-size vs 80×24 stale-viewport) in STATUS

## Accept
- (a) stale viewport references updated to 80×25/82×27
- (b) terminal-size ≥80×24 references untouched
- (c) historical PREP narratives honest (annotated, not rewritten)
- `rg '80×24|80x24|82×26|82x26' workorders/` each hit labeled (a)/(b)/(c) in STATUS

## Refs
hub HANDOFF @ 00:22:20Z · hub Accept `0ea5e74` + Push GO @ 00:25:33Z · Cursor STATUS DONE @ 00:24:30Z · PUSHED + CLOSED @ 00:25:45Z
