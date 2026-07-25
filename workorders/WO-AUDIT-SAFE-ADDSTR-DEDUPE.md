# WO-AUDIT-SAFE-ADDSTR-DEDUPE — Unify screens._safe_addstr with draw choke

> Status: **DRAFT** 2026-07-25 · from CC POLISH Zone-A BANK · tip `88004d8`  
> Type: polish · Priority: P2 · Lens: L4  
> Refs: `screens.py:_safe_addstr` (~255) · `cockpit/draw.py:_safe_write`

## Goal
Retire the less-hardened `screens._safe_addstr` duplicate: reuse draw choke (control-char sanitize + cell-width clip) for operator-typed echo and bank metadata.

## Scope
- A: `screens.py` — call into draw helper / shared util
- B: `cockpit/draw.py` — export if needed; keep one choke
- C: tests — echo/clip matrix; no visual seat-key change

## Constraints
3-screen rendering change → own WO (this). No attach/M semantics. No HARDEN reopen.

## Accept
One write primitive; `_safe_addstr` gone or thin wrapper; clip/sanitize parity with draw.

## Proof
Unit + optional pty · STATUS. Push waits Accept.

## Refs
CC Zone-A @ 05:27:02Z
