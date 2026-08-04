# WO-AUDIT-BUILD-SECTOR-THREAT-FIGHTERS-GUARD-INPUT

**Status:** CLAIMED by `impl-aiclient-cursor` (`📋 CLAIM` 2026-08-04T18:35:58Z)
**Priority:** MED
**Depends-on:** none
**Gated:** no

## Goal

Extend the route-hazard STOP guard so known world-model sector threats
(`threats.mines` / `threats.fighters`) block planned crossings the same way
one-way / warp-sink hops already do — never silent drive-through, never
autonomous reroute.

## Note on audit premise

Queue text said mines were already a guard input; tip code only covered
formation one-way / warp-sink. This WO wires **both** mines and fighters
(canon `toll-and-defense.md` already required mines; Accept named fighters).

## Scope

- `tw2002_aiclient/formations.py` — `threat_hazard_for_sector` +
  `route_hazard_for_hop(..., threats_by_sector=)`
- `tw2002_aiclient/explore.py` — pass threats index into the explore guard
- `tw2002_aiclient/trade_adapter.py` / `trade_driver.py` — path exclude +
  ChainHold scan
- `canon/engine/priority-engine.md` — flip sector-threats row honesty
- pins + this WO file

## Accept

1. Destination with `mines: True` → `route_hazard:mines:<id>`
2. Destination with fighters count `> 0` → `route_hazard:fighters:<id>`
3. `fighters: None` / `0` → not a hazard
4. Explore / trade path consumers honor the new reasons (STOP / exclude)
5. live-prove: `n/a` (offline guard predicate + path exclude)

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_sector_threat_route_hazard.py \
  tests/test_route_hazard_guard.py \
  tests/test_trade_hazard_path_exclude.py \
  -q
```

## Refs

- queue-aiclient.md `AUDIT-BUILD-SECTOR-THREAT-FIGHTERS-GUARD-INPUT`
- `canon/strategy/toll-and-defense.md` (mines/fighters as route-hazard STOP)
- `WO-ROUTE-HAZARD-GUARD` / `WO-TRADE-HAZARD-PATH-EXCLUDE`
