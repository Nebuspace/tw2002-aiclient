# WO-AUDIT-CANON-FIX-STALE-STARDOCK-LANDMARK-STATUS

**Status:** CLAIMED by `impl-aiclient-cursor`
**Priority:** MED
**Depends-on:** none (WO-WM-LANDMARKS-WRITE already shipped)
**Gated:** no — canon honesty only

## Goal

Flip `priority-engine.md` row #3 off **Starved**: landmark writer + `WorldStats` status merge exist;
GOALS can show `StarDock @…` when landmarks are present.

## Scope

- `canon/engine/priority-engine.md` (row #3 + honesty note)
- This WO file

## Accept

1. Row #3 no longer claims "no writer" / blocked on landmarks-write.
2. Residual honesty named (omit-until-known empty scan).
3. live-prove: `n/a` (docs only).

## Proof

Diff review vs `world_model.add_landmark` / `sector_explore` / `world_stats`. STATUS with SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-FIX-STALE-STARDOCK-LANDMARK-STATUS`
- `tw2002_aiclient/world_model.py` ~375 · `session/sector_explore.py` ~673
