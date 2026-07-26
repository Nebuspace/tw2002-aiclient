# WO-P2-G4-X5-STOP-LOSS-FLOOR

**Status:** DONE · origin `470ed3c`  
**Posted:** 2026-07-26 · M3 slice X5 (stub)

## Goal

Credits observation for the stop-loss rail (`--floor`). Prefer **refuse a floor the runtime cannot enforce** over accepting a decorative flag.

## Scope

- Credits / observation substrate + CLI flag honesty
- Pins: refuse vs enforce — never accept `--floor` without enforcement

## Constraints

- **Accept pin:** *accepting a `--floor` it cannot enforce is much easier to write than refusing it, and it reads as a feature* — that cheat is forbidden
- Deferrable only if X1/slice-1 refuses `--floor` outright
- No invent trade loop

## Accept

Either enforced floor with observation pins, or explicit refuse of `--floor` with honest help/error; no decorative accept.

## Proof

STATUS + SHA · targeted pytest.

## Refs

CC G4 six-slice 2026-07-26T03:17:33Z · M3 X5
