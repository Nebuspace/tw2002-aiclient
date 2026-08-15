# WO-CANON-DRAFT-AUTOHAGGLE-DEFAULT-OFF-CAVEAT

**Status:** docs caveat  
**Branch:** `wo/CANON-DRAFT-AUTOHAGGLE-DEFAULT-OFF-CAVEAT`  
**Seat:** impl-aiclient-h1

## Goal

Fold a scoped caveat into canon so auto-haggle.md / action-safety-guards.md no longer read as
unconditional ON-by-default against tip `TradeDriverConfig.auto_haggle=False` (PWO-087 / #360).

## Scope

- `canon/engine/auto-haggle.md` — caveat under § On-by-default, guarded
- `canon/doctrine/action-safety-guards.md` — matching caveat after the ON-BY-DEFAULT lead-in
- `workorders/ULTRACODE-WO-INVENTORY.md` PWO-087 — cross-ref the caveat (closes sibling
  WO-CLEANUP-WO-INVENTORY-PWO087-CROSSREF in the same edit, per that row's "fold in alongside")

## Accept

- Canon distinguishes rule-macro ON-by-default from TradeChainRunner opt-in OFF.
- Tip cites: `trade_driver.py` `auto_haggle: bool = False`, PWO-087 / merge #360.
- Inventory PWO-087 row points at the caveat.

## Proof

- Docs-only → live-prove `n/a`.
