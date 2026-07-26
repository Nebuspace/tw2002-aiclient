# WO-P2-G4-X3-LOOP-PLAYER

**Status:** DONE · origin `a7dbf22`  
**Posted:** 2026-07-26 · M3 slice X3 (stub)

## Goal

`loops/player.py` — replay one taught loop: re-check `start_anchor` against current sector **before any send**, then per-step confirm → halt-with-trace on mismatch / unknown / never-auto mid-loop.

## Scope

- `tw2002_aiclient/loops/player.py` (+ tests)
- Consumes X2 loader + X1 state/sector read
- No daemon background player (X4) · no writer (X6)

## Constraints

- Stop-on-unknown · zero bytes on unrecognized screen
- Unattended replay must refuse `NEVER_AUTO_ACTION_CLASSES` mid-loop (§A.2 — macros have no guard field)
- No invent `autoloop` CLI verb here
- Cite macros.md · screen/archive patterns

## Accept

Anchor pre-check gates first send; halt-with-trace on failure; pins green; package keystroke pin respected except through explicit player API under test.

## Proof

STATUS + SHA · targeted pytest.

## Refs

CC G4 six-slice table 2026-07-26T03:17:33Z · macros.md start_anchor · M3 X3
