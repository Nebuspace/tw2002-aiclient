# WO-CANON-FIX-SHIP-PROGRESSION-CATALOG-MAX-HOLDS-TIP-TRUE

**Status:** IN FLIGHT · Cursor · `wo/CANON-FIX-SHIP-PROGRESSION-CATALOG-MAX-HOLDS-TIP-TRUE`
**Posted:** 2026-08-10 · impl-aiclient-cursor (verify-first residual after #654)

## Goal

Tip-true `canon/strategy/ship-progression.md` against the already-shipped catalog
`max_holds` auto-max clamp (`WO-FIX-STARDOCK-HOLD-CLAMP-CATALOG-LOOKUP` / PR #535).

## Verify-first

- Tip `stardock_hold_plan._auto_max_room` / `plan_from_status(..., auto_max=True)` prefer
  Layer-B catalog `max_holds − current_holds` when resolvable; else HUD empty
  (fail-closed).
- Tip prose still said catalog max "is not yet required" — DOCS WIN residual.

## Scope

- `canon/strategy/ship-progression.md` — TW-22 auto-max bullet + tip-module table row
- `workorders/WO-CANON-FIX-SHIP-PROGRESSION-CATALOG-MAX-HOLDS-TIP-TRUE.md` — this file

## Out of bounds

- No code / clamp behavior change
- No affordability-explore numeric thresholds (still Pending)

## Accept

1. Canon no longer claims catalog `max_holds` is unused / "not yet required" for auto-max.
2. Prose matches tip prefer-catalog / HUD-fallback contract.
3. live-prove `n/a` (docs-only).

## Refs

- `tw2002_aiclient/stardock_hold_plan.py` (`_catalog_max_holds_from_status`, `_auto_max_room`)
- queue DONE row `WO-FIX-STARDOCK-HOLD-CLAMP-CATALOG-LOOKUP` (`b721fa2` / #535)
