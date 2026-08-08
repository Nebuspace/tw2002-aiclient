# WO-CANON-FIX-PRIORITY-ENGINE-STALE-HOLD-EXECUTE-ROW

**Status:** IMPLEMENTING
**Posted:** 2026-08-08 · IDLE-KICK MED continuation after #571 merged

## Goal

Tip-correct priority-engine catalog row #8: it still says
`Planned — … EXECUTE navigation-only` while tip ships a real confirm-armed
StarDock hold buy (`stardock_hold_driver.run_hold_purchase` +
`session/stardock_hold.StardockHoldRunner`). Docs win — tense/status only.

## Scope

- `canon/engine/priority-engine.md` — row #8 status cell (and any adjacent prose
  that still claims hold EXECUTE is navigation-only / unbuilt).
- This WO markdown.

## Constraints

- Docs-only. No code / driver behavior changes.
- Do not invent new weights or promote row #8 to “fully done” beyond what tip
  actually wires (confirm-armed one-pass buy; decision/ROI still Partial).

## Accept

1. Row #8 no longer claims EXECUTE is navigation-only.
2. Status cites the live driver modules by name.
3. live-prove **n/a** (docs).

## Proof

Diff review of `canon/engine/priority-engine.md` vs tip `stardock_hold_driver.py`
/ `session/stardock_hold.py`.
