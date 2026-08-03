# WO-ROUTE-HAZARD-GUARD — STOP before crossing known route hazards

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T01:05:00Z  
**Branch:** `wo/ROUTE-HAZARD-GUARD`  
**Zone:** `tw2002-aiclient` only  
**Refs:** `canon/strategy/special-formations.md` Dual consumer split ·
`action-safety-guards.md` hazard rail · #325/#326 membership · prior retract of
anti-canon `WO-EXPLORE-AVOID-ONE-WAY`

## Goal

Wire formation **route hazards** into a **guard that STOPs** — never an
autonomous reroute. When the explore seam is about to send a hop that crosses a
known one-way edge or enters a warp-sink sector, halt with a typed
`route_hazard:…` reason and hand the keyboard back (no alternate path search).

## Scope

- `tw2002_aiclient/formations.py` — pure `route_hazard_for_hop`
- `tw2002_aiclient/explore.py` — check before returning a warp target
- `tw2002_aiclient/session/sector_explore.py` — preserve `route_hazard:` halt
  reasons (do not wrap as `explore_exhausted:…`)
- `tests/` — hop predicate + explore halt pin
- `workorders/WO-ROUTE-HAZARD-GUARD.md` — this file

## Constraints

- **No silent path avoid / fail-open alternate route** (canon forbids it)
- Trade-driver wire deferred unless the same one-line seam fits Accept
- No Play E-cycle / ARMABLE widen (#247)
- Explicit paths — never `git add -A`

## Accept

1. Pure: A→B with no reverse among known → `route_hazard:one_way:A→B`
2. Pure: hop into `warp-sink` membership → `route_hazard:warp_sink:N`
3. Explore `map_fill` / intent seam: hazardous next hop → `(None, route_hazard:…)`
   / `IntentTick` with that reason — no alternate hop chosen that tick
4. Runner reports `route_hazard:…` without `explore_exhausted:` prefix
5. Focused tests green; live `n/a` (offline guard)

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_route_hazard_guard.py \
  tests/test_explore.py \
  tests/test_formations_catalog.py \
  -q
```
