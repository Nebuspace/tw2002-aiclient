# WO-CONN-CHIP-PTY-PROOF — CONN control-strip chip Layer-B content proof

**Status:** OPEN · READY  
**Posted:** 2026-07-27T14:55:00Z · hub refill after draw-wire sweeps  
**Seat:** open — CC origin; Cursor if CC lane full  
**Depends:** `main` ≥ `2920ef7` (wire-sweep + arm honesty)  
**Refs:** CC panel/chip sweep 2026-07-27 · `tests/test_cockpit_covermeter_pty.py` pattern

## Goal

Pin that the **CONN** chip is wired through `screens.py` to the live control strip (not composer-only).

## Scope

- Add `tests/test_cockpit_conn_pty.py` (Layer-B PTY harness; assert CONN text on strip)
- Deletion/wire-gap pin: removing `conn_chip=` from draw path must go red (wire-sweep or inline mutation pin)

## Constraints

- No behaviour change unless a real wiring bug is found; if found, fix + pin in same PR.
- Do not touch canon (#93) in this WO.

## Accept

1. PTY test fails if `conn_chip` wire removed (proves reachability).
2. Full suite green on PR tip.
3. PR + STATUS.

## Proof

`pytest tests/test_cockpit_conn_pty.py` + suite CI.
