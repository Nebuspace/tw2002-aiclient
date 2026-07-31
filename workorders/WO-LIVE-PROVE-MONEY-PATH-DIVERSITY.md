# WO-LIVE-PROVE-MONEY-PATH-DIVERSITY

**Goal:** Run hub live-prove diversity for money-path arms already on main
(guarded trade chain #267 · StarDock hold #279) across ≥3 catalog hosts
with ≥1 NEW and ≥1 RETURNING across the run.

## Why

Offline Accept shipped; live diversity was **BANKED** (NOT-ATTEMPTED) at
merge. Operator autonomy path needs live evidence before trusting
turn-spend on TWGS.

## Fix

1. Max sacrificial GO for turn-spend cells.
2. Cursor (or hub) executes safe half first (transport/attach); then
   diversity arm under Max GO.
3. Post via `scripts/hub-live-prove-check.sh` with host keys + NEW/RETURNING
   counts (no secrets).

## Accept

1. Diversity bar met OR honest SKIP cells with reason.
2. Never record NOT-ATTEMPTED as `n/a`.
3. Status posted to coord + Commit Status / Check Run.

## Scope

- live runbook evidence only (no product code required)
- `workorders/WO-LIVE-PROVE-MONEY-PATH-DIVERSITY.md`

## Constraints

- Max-gated turn-spend · hub GO for safe halves
- Seat class: Cursor for live execution

## Proof

live-prove success summary listing hosts + NEW/RETURNING.

## Refs

- `.cursor/rules/live-prove-pushback.mdc`
- #267 · #279 · `.samantha/plans/full-autonomy-early-game.md` step 6
