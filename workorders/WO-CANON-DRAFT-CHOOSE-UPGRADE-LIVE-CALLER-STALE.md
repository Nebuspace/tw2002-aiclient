# WO-CANON-DRAFT-CHOOSE-UPGRADE-LIVE-CALLER-STALE — tip-stamp FOCUS caller

**Status:** IN FLIGHT · Cursor · `wo/CANON-DRAFT-CHOOSE-UPGRADE-LIVE-CALLER-STALE`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Fix `canon/strategy/ship-progression.md` claim that a live FOCUS-tick flow
calling `choose_upgrade` is still missing — tip `cockpit/decisions.py` already
calls `upgrade_decision_from_status` → `choose_upgrade` when status inputs
exist. Residual is status producers for those inputs, not the caller.

## Accept

1. Divergence note names the live FOCUS coach caller and the missing
   `upgrade_catalog` / `upgrade_player` / `upgrade_loop` producers.
2. live-prove `n/a` (docs-only).

## Refs

- `cockpit/decisions.py:189-202` · `ship_upgrade_decision.py:373-466`
