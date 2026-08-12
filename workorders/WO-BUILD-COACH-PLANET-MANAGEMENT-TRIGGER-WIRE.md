# WO-BUILD-COACH-PLANET-MANAGEMENT-TRIGGER-WIRE

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** MED  
**Refs:** `canon/engine/coaching-engine.md` · `data/coach/strategies.json` (`planet_production`) · `world_stats.WorldStats` · `coach_engine.infer_coach_triggers` · `cockpit/decisions.py`

## Goal

Wire an honest `planet_management` boolean onto status so the authored
`planet_production` coach card can fire. Tip previously emitted seven of eight
strategy triggers; `planet_management` was the last authored-unreachable gap.

## Scope

- `world_model.OWN_PLANET_LANDMARK` + `WorldStats` True-or-omit merge of
  `planet_management=True` when `find_landmark_sectors(..., own_planet)` is
  non-empty (mirrors `has_port` / StarDock honesty — never invents `False`).
- `infer_coach_triggers(planet_management=…)` identity-true only.
- `cockpit/decisions.py` passes the status key through.
- Canon + `strategies.json` status flip to wired; reachable-card pin updated.

## Accept

1. Own-planet landmark on disk → status carries `planet_management=True` after
   `WorldStats.refresh` → DECISIONS renders the planet production card.
2. Absent / empty / junk / non-identity-true → no card (fail-closed).
3. Authored trigger set ≡ emitted trigger set (empty-set difference pin).

## Proof

```bash
.venv/bin/python -m pytest tests/test_coach_engine.py tests/test_world_stats.py \
  tests/test_cockpit_decisions.py -n0 -q -k 'planet_management or reachable_trigger'
```

live-prove: n/a for pure offline coach/status wiring unless hub asks for a
safe attach half.
