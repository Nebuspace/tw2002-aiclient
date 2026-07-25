# WO-AUDIT-P025-LEDGER-HONESTY — Control-lock actor tag / ledger gap

> Status: **EXECUTED** 2026-07-25 · AUDIT docs tick · tip inventory **PARTIAL**  
> Type: docs + thin PREP · Priority: P1 · Lens: L1 / L3  
> Refs: ULTRACODE PWO-025 · `session/daemon.py` “LedgerWriter deferred” · `session.py` `VALID_SENDERS`

## Tip verdict
**PARTIAL** — `control_lock` modes `{app,human,spectate}` + send-time `VALID_SENDERS = ("app","human")` are LIVE on tip. Accept’s *ledger rows actor∈{app,human}* is **MISSING**: `daemon.py` still defers `LedgerWriter` / `record_attach_keystroke`. Product ledger remains a follow-on (overlaps PWO-094). ULTRACODE row stamped PARTIAL (not DONE).

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
