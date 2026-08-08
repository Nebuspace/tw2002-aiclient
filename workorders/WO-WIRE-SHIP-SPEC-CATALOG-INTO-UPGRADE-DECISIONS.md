# WO-WIRE-SHIP-SPEC-CATALOG-INTO-UPGRADE-DECISIONS

**Status:** IN FLIGHT · Cursor · `wo/WIRE-SHIP-SPEC-CATALOG-INTO-UPGRADE-DECISIONS`  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `0007750` (PR #471 ship_spec adapter + GameDataStats live)  
**Refs:** queue-aiclient.md · `ship_upgrade_decision.ship_spec_from_current_info` ·
`cockpit/decisions.py` upgrade consumer · `canon/strategy/ship-progression.md` § Code divergence

## Goal

Wire live `GameData.ships` + `ship_spec_from_current_info` into the status keys
`upgrade_catalog` / `upgrade_player` / `upgrade_loop` so
`cockpit/decisions.py` → `upgrade_decision_from_status` → `choose_upgrade` sees
real Layer-B catalog data instead of only test-constructed inputs.

## Scope

1. **Producer:** extend `GameDataStats` (already loads Layer-B `game_data`) to
   emit a full `upgrade_catalog` (ShipSpec-shaped dicts via `ship_row_to_spec`)
   plus `upgrade_cost_per_hold` when a hold quote exists.
2. **Player:** when status carries `current_ship` + `turns_left`, build
   `upgrade_player` using live holds/fighters; call
   `ship_spec_from_current_info(info, catalog=GameData.ships)` for catalog
   match enrichment (cost/shields never invented from I-info alone).
3. **Loop:** when a priced `ProfitChain` is available (via `FocusScalars` /
   `ChainScalars`), emit honest `upgrade_loop` from chain
   `overall_profit` / `turns`; stock gate uses
   `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE` (short chain → capacity capped at
   current holds; long chain → defer stock to ROI). Omit when incomplete.
4. **Tests** covering catalog merge + player enrichment + end-to-end DECISIONS
   surface when all three inputs are present.
5. Recommend-only — no purchase send path.

## Constraints

- Never invent catalog cost/shields from I-info alone.
- Never invent loop margin/turns without a priced chain.
- AI never live-drives; DECISIONS remains display-only.
- Explicit-path commits only; no secrets; no operator-home paths.

## Accept

1. With persisted `GameData.ships` + live `current_ship` + priced chain on the
   status merge path, `upgrade_decision_from_status` returns a non-`None`
   `UpgradeDecision` (recommend or HOLD with rationale).
2. `ship_spec_from_current_info` is called with the live GameData ships catalog
   (not only test fixtures).
3. Absent/incomplete inputs stay omit/fail-closed (no invented margins).
4. Focused pytest green; live-prove `n/a` (recommend-only chrome; no money send).

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_ship_upgrade_decision.py \
  tests/test_game_data_stats.py \
  tests/test_upgrade_status_wire.py \
  -q -n0
```

live-prove: `n/a` — offline recommend-only status merge; no TWGS arm.
