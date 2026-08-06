# WO-BUILD-LIVE-SHIP-INTROSPECTION-ADAPTER

**Status:** IN PROGRESS  
**Priority:** MED  
**Gated:** no (hub GO 2026-08-06 Cycle-42 core-mechanics greenlight)

## Goal

Bridge live `I` ship-info screens into current-ship type identification
(priority-engine row 2) and optional `ShipSpec` for upgrade scoring — never
inventing catalog cost/shields from the info screen alone.

## Scope

- `tw2002_aiclient/introspector.py` — `parse_current_ship_info`
- `tw2002_aiclient/game_data.py` — `ship_row_to_spec` (canon-named bridge)
- `tw2002_aiclient/ship_upgrade_decision.py` — `ship_spec_from_current_info`
- `tw2002_aiclient/session/session.py` + `protocol.py` + `hud_seed.py` — observe/emit
- `canon/engine/priority-engine.md` — tip-stamp row 2 Partial (live-bridged)
- Tests against `tests/fixtures/ship_info_screen.txt`

## Accept

1. `parse_current_ship_info(ship_info_screen.txt)` yields `ship_type` without Ported/Kills.
2. Status emits `ship_type` / `current_ship` omit-until-known after observe.
3. `ship_spec_from_current_info` returns `None` without catalog match; with match uses live holds/fighters + catalog cost/shields.
4. Recommend-only — no purchase send path.
5. live-prove: n/a for pure adapter offline; optional status observe on live later.

## Proof

```bash
.venv/bin/python -m pytest tests/test_introspector.py tests/test_game_data.py tests/test_ship_upgrade_decision.py -q -n0
```
