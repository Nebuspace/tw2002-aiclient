# WO-FIX-STARDOCK-HOLD-CLAMP-CATALOG-LOOKUP

**Goal:** `stardock_hold_plan.py`'s `_autonomy_auto_fire` auto-max-holds clamp
uses only currently-observed empty holds (visible headroom), not the ship's
true Layer-B catalog `max_holds` ceiling — softer than the rest of
ship-progression's fail-closed posture, which never invents cost/shields from
I-info alone but should still bind against the ship's real known max.

**Scope:**
- `tw2002_aiclient/stardock_hold_plan.py` — wire the catalog `max_holds`
  lookup into the auto-max clamp
- Tests covering the clamp behavior with and without a resolved catalog entry

**Constraints:**
- If no catalog entry is resolvable for the current ship, fall back to the
  existing observed-headroom behavior (fail-closed, never fabricate a max)
- Do not touch cost/shields fields — this WO is holds-only

**Accept:**
- Clamp uses catalog `max_holds` when resolvable, falls back safely otherwise
- Tests cover both paths

**Refs:** canon/strategy/ship-progression.md:196-206; 6-lens aiclient audit 2026-08-08T02:12Z
