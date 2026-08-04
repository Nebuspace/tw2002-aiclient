# WO-AUDIT-BUILD-TW22-AUTO-MAX-HOLDS

**Status:** CLAIMED by `impl-aiclient-cursor` (post-#378 next pick)
**Priority:** MED
**Depends-on:** WO-WM-LANDMARKS-WRITE + AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP (landed)
**Gated:** no — reuses existing confirm / App-armed hold path; no new spend verb

## Goal

Implement TW-22 coded auto-max-holds: when Cargo Hold Upgrade is App-armed,
plan qty expands toward empty-hold capacity as credits allow (after cash floor),
not a hard-coded `qty=1`.

## Scope

- `tw2002_aiclient/stardock_hold_plan.py` — `compute_auto_max_qty`, `plan_from_status(..., auto_max=)`
- `tw2002_aiclient/app.py` — `_autonomy_auto_fire` uses `auto_max=True`
- `tests/test_stardock_hold_plan.py`
- `canon/strategy/ship-progression.md` divergence honesty
- This WO file

## Out of scope

- Changing App-armed skip-confirm policy (existing WO-PLAY-STRIP-POLICY-AUTO DECISION)
- Ship-hull upgrade execute / Layer-B `max_holds` catalog lookup (HUD empty is room-to-max)
- Manual `H` qty=1 path (unchanged)

## Accept

1. `plan_from_status(..., auto_max=True)` returns qty = min(empty, spendable//price).
2. App-armed hold auto-fire passes that qty into `stardock_hold_start`.
3. Manual / default `plan_from_status` still qty=1.
4. Pins cover compute + status string empty-holds.
5. live-prove: `n/a` or DEFERRED — offline plan math; no new live send.

## Proof

`pytest tests/test_stardock_hold_plan.py` + suite green. STATUS with SHA.

## Refs

- `canon/strategy/ship-progression.md` § Coded auto-max-holds (~115–136)
- queue-aiclient.md `AUDIT-BUILD-TW22-AUTO-MAX-HOLDS`
