# WO-AUDIT-P025-LEDGER-HONESTY — Control-lock actor tag / ledger gap

> Status: **DRAFT** 2026-07-25 · AUDIT-OKF-6LENS · tip `d4a8829`  
> Type: docs + thin PREP · Priority: P1 · Lens: L1 / L3  
> Refs: ULTRACODE PWO-025 · `session/daemon.py` “LedgerWriter deferred”

## Goal
Make tip honesty explicit: control_lock `{app,human,spectate}` LIVE; attach keystroke ledger / `LedgerWriter` still MISSING — so PWO-025 is PARTIAL, not silently DONE.

## Scope (disjoint)
- A: `workorders/ULTRACODE-WO-INVENTORY.md` — 025 status PARTIAL + cite daemon deferral
- B: `workorders/WO-AUDIT-P025-LEDGER-PREP.md` (optional nested) or section here — Accept/Proof for future LedgerWriter port
- C: findings cross-link if unsigned

## Constraints
No product ledger implementation in this WO unless hub splits a product HANDOFF. No secrets in ledger design. Dedup vs PWO-041 LOGS band (tail exists; per-dispatch schema is 094/025).

## Accept
Inventory no longer implies 025 fully satisfied; deferred symbols named (`ledger.py` / `record_attach_keystroke`).

## Proof
Docs commit; `rg` for honest PARTIAL. Push waits Accept.

## Refs
`daemon.py:11-13,100` · canon `trace-ledger.md` · PWO-041 / PWO-094
