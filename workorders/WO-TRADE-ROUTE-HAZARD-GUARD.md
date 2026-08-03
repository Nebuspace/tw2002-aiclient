# WO-TRADE-ROUTE-HAZARD-GUARD — ChainHold before crossing route hazards

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T01:12:30Z  
**Branch:** `wo/TRADE-ROUTE-HAZARD-GUARD`  
**Zone:** `tw2002-aiclient` only  
**Refs:** #327 explore STOP · `canon/strategy/special-formations.md` Dual
consumer · `trade_driver._navigate` · Accept note on #327

## Goal

Same Dual-consumer STOP as explore: when trade `_navigate`'s planned path
would cross a known one-way or enter a warp-sink, **ChainHold** before any
send — never silent detour.

## Scope

- `tw2002_aiclient/trade_driver.py` — pre-send path scan via
  `route_hazard_for_hop`; membership from world_model when available
- `tests/` — one-way HOLD pin (no send)
- `workorders/WO-TRADE-ROUTE-HAZARD-GUARD.md` — this file

## Constraints

- No alternate-path search on hazard
- Reuse `formations.route_hazard_for_hop` (#327) — no second detector
- Explicit paths — never `git add -A`

## Accept

1. Planned path with one-way edge → `ChainHold` matching `route_hazard:one_way:…`
2. No sector send issued for that navigate call
3. Existing warp_confirm Y/N pins still green
4. Focused tests green; live `n/a`

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_trade_route_hazard_guard.py \
  tests/test_trade_warp_confirm_y.py \
  tests/test_route_hazard_guard.py \
  -q
```
