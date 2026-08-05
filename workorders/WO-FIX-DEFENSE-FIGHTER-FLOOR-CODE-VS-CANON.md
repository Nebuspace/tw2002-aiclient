# WO-FIX-DEFENSE-FIGHTER-FLOOR-CODE-VS-CANON

**Status:** DONE (pending merge)
**Priority:** LOW
**Gated:** no (docs honesty; no new defense constant)

## Goal

Stop toll-and-defense.md presenting `defense_fighter_floor` /
`keep_min_defense_fighters=20` as if tip-real. Tip only ships
`DEFAULT_FIGHTER_RESERVE=5`.

## Scope

- `canon/strategy/toll-and-defense.md` schema + reserve-floor prose
- This WO file

## Accept

1. Schema marks the 20-fighter upgrade floor as NOT ON TIP / unbuilt.
2. Prose names only `DEFAULT_FIGHTER_RESERVE` as the live clamp.
3. live-prove: `n/a` (docs-only).

## Proof

`rg defense_fighter_floor|keep_min_defense` → canon honesty only; no new `.py`.
