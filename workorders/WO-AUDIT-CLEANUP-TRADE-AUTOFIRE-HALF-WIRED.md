# WO-AUDIT-CLEANUP-TRADE-AUTOFIRE-HALF-WIRED

**Status:** CLAIMED by `impl-aiclient-cursor` (`📋 CLAIM` 2026-08-04T18:26:22Z)
**Priority:** MED
**Depends-on:** none
**Gated:** no

## Goal

Remove abandoned Port Trade auto-fire cooldown scaffolding: `_arm_trade_auto_fire_cooldown` mutated state with zero callers of the paired gate `_trade_auto_fire_cooldown_active`. Bank-delete sibling `_prefer_explore_while_trade_blocked` (fully implemented, zero callers).

## Intent (confirmed)

Silent FOCUS `run_chain` auto-fire is intentionally refused (`RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES` / early `return False` in `_autonomy_auto_fire`). Wiring the cooldown check into a path that never auto-fires trade would be costume. Remove setter+getter+arm site+backoff helpers as abandoned scaffolding, not half-wire-forward.

## Scope

- `tw2002_aiclient/app.py` — delete cooldown/backoff/prefer-explore helpers and the idle-loop `auto_fire_kicked_explore` bridge that only prefer-explore set
- Keep `_trade_auto_fire_map_marker` (still used for bubble subject sector)
- This WO file + pin test
- Sibling queue row `AUDIT-CLEANUP-PREFER-EXPLORE-TRADE-BLOCKED-DEAD` closed by the same change

## Accept

1. `_arm_trade_auto_fire_cooldown`, `_trade_auto_fire_cooldown_active`, `_trade_auto_fire_reason_is_backoff`, `_prefer_explore_while_trade_blocked`, and `auto_fire_kicked_explore` are absent from product code.
2. `_trade_auto_fire_map_marker` remains and still has callers.
3. live-prove: `n/a` (dead-code cleanup only; no live send path change).

## Proof

`rg` clean on removed symbols + pin test + suite. STATUS with SHA.

## Refs

- queue-aiclient.md `AUDIT-CLEANUP-TRADE-AUTOFIRE-HALF-WIRED` + `AUDIT-CLEANUP-PREFER-EXPLORE-TRADE-BLOCKED-DEAD`
- `workorders/WO-EXPLORE-TRADE-MODE-SPLIT.md` (prefer-explore neutralization)
