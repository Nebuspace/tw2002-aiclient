# WO-AUDIT-LOG-NOTE-RETIRE-OR-WIRE — logging_util.log_note fate

> Status: **Ruled RETIRE** 2026-07-25 · Max Batch 2/3 · Priority: P2  
> Refs: `session/logging_util.py` `log_note` · zero production callers

## Ruling
**`log_note` → RETIRE** (delete dead helper; no silent keep). Product delete + callers/tests = CC
(`WO-AUDIT-LOG-NOTE-RETIRE` / follow-on after 061). Docs note only on this seat.

## Proof
findings + backlog stamp. Push waits Accept.
