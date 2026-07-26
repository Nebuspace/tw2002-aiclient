# WO-P2-G4-AUTOLOOP

**Status:** CLOSED — BLOCKED ON SUBSTRATE (zero code, by design) · X1-X6 named  
**Posted:** 2026-07-26T00:55:00Z  
**Depends:** G3 `tw loops` on help (landed `1c084e5` / `385b176`)

## Goal

Ship `tw autoloop` (+ `loop_player` substrate as needed): App drives a taught loop under control_lock, stops on unknown / escalate, never invents loops.

## Outcome (2026-07-26T03:17:33Z CC)

**Blocked:** canon requires current-sector read before every replay send — `state_parser` / `state` verb **absent**. Accept #2 structurally unreachable. Macro store has no guard/arm fields → §A.2 human-armed exemption unexpressible for `tw autoloop <name>`.

**Follow-on slices (M3):** X1 state read · **X2 loader (GO)** · X3 player · X4 daemon+verbs · X5 floor · X6 record writer. See coord STATUS + `WO-P2-G4-X2-LOOP-STORE-LOADER.md`.

## Refs

CC STATUS 2026-07-26T03:17:33Z · hub Accept blocked-on-substrate · north-star · macros.md start_anchor
