# WO-CANON-FIX-RECOMMEND-GENESIS-TIP-TRUE

**Status:** IN FLIGHT · Cursor · `wo/CANON-FIX-RECOMMEND-GENESIS-TIP-TRUE`
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ `f2a8f607` (#659 MERGED)
**Refs:** residual of WO-BUILD-FORMATIONS-GENESIS-RECOMMEND-VERIFY ·
`canon/engine/world-model.md` · `canon/strategy/special-formations.md` ·
`canon/strategy/planet-colonization.md` · `explore.plan_find_formations` ·
`world_stats.WorldStats.refresh`

## Why

#659 wired `formations.recommend_genesis` into product recommend paths
(`explore.plan_find_formations`, `WorldStats.refresh` → `genesis_count`).
Three canon Code-reality / world-model bullets still claim the alias has
"no separate auto-caller" / no product surface beyond the catalogue — tip-false
after #659.

## Goal

Tip-true citation flip only. Preserve RECOMMEND-only doctrine (no deploy send).

## Scope

1. `canon/engine/world-model.md` — name #659 explore + WorldStats callers.
2. `canon/strategy/special-formations.md` § Code reality — same.
3. `canon/strategy/planet-colonization.md` — replace "no product surface that
   auto-invokes beyond catalogue" with tip-true shared-consumer wording.
4. This WO file.

## Out of scope

- Genesis deploy / Option B confirm UI.
- Changing `recommend_genesis` semantics (still alias of `genesis_candidates`).
- Ledger / unused-code disposition (hub-local).

## Accept

1. Three canon passages no longer claim zero product callers.
2. Explicitly keep "no autonomous deploy".
3. Docs-only · live-prove n/a · path-leak clean.

## Proof

- `git grep recommend_genesis origin/main -- tw2002_aiclient` shows explore.py + world_stats.py callers.
- Diff limited to the three canon files + this WO.
