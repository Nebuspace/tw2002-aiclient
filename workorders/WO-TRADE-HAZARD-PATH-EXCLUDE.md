# WO-TRADE-HAZARD-PATH-EXCLUDE — Drop hops whose shortest path is hazardous

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T01:23:00Z  
**Branch:** `wo/TRADE-HAZARD-PATH-EXCLUDE`  
**Zone:** `tw2002-aiclient` only  
**Refs:** #328 navigate STOP · Dual-consumer (exclude ≠ reroute) ·
`trade_adapter.build_trade_hops` / `build_candidate_pairs`

## Goal

Do not surface trade hops / candidate pairs whose **shortest** known path
crosses a one-way or warp-sink. Autopilot must not arm a chain that will
`ChainHold` on first navigate. No alternate-path search.

## Scope

- `tw2002_aiclient/trade_adapter.py` — `_path_has_route_hazard` filter
- `tests/` — one-way path excluded from hops
- `workorders/WO-TRADE-HAZARD-PATH-EXCLUDE.md` — this file

## Constraints

- Exclude only; never BFS around the hazard
- Reuse `formations.route_hazard_for_hop`
- Explicit paths — never `git add -A`

## Accept

1. Hop whose only/shortest path is one-way → absent from `build_trade_hops`
2. Bidirectional pair with a hazardous leg → absent from `build_candidate_pairs`
3. Safe-path hops unchanged
4. Focused tests green; live `n/a`

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_trade_hazard_path_exclude.py \
  tests/test_trade_adapter.py \
  tests/test_trade_route_hazard_guard.py \
  -q
```
