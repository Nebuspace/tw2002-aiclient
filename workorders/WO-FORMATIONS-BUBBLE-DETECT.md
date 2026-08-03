# WO-FORMATIONS-BUBBLE-DETECT — Port bubble topology into shared detector

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T00:25:38Z  
**Branch:** `wo/FORMATIONS-BUBBLE-DETECT`  
**Zone:** `tw2002-aiclient` only  
**Refs:** #317 dead-end-only · #323 `formations_from_sectors` · `canon/strategy/special-formations.md` · archive `twclient/formations._bubbles`

## Goal

Extend the shared formations detector past dead-ends: catalogue **bubbles**
(single-entrance pockets, size ≥2 interior) so FORMATIONS panel, GOALS /
`genesis_count`, and `plan_find_formations` all see them from one pass.

## Scope

- `tw2002_aiclient/formations.py` — port archive `_bubbles` (+ undirected helper);
  `formations_from_sectors` emits dead_ends + bubbles; panel mapper names bubbles
- `tests/test_formations_catalog.py` — archive bubble fixture + genesis inclusion
- `workorders/WO-FORMATIONS-BUBBLE-DETECT.md` — this file

## Constraints

- One-ways / warp-sinks stay deferred (hazard consumers, separate WO)
- Do **not** widen Play E-cycle / `ARMABLE_INTENTS` (#247)
- Kind strings stay snake_case (`dead_end`, `bubble`) — not archive hyphens
- LOCATE / CATALOG / RECOMMEND only — no Genesis deploy / claim
- Explicit paths — never `git add -A`

## Accept

1. Archive bubble fixture catalogues exactly one bubble with expected members + entrance
2. Bubbles appear in `genesis_candidates` and panel items
3. Dead-end behaviour unchanged on graphs without bubbles
4. Focused tests green; live `n/a` (offline topology; no live send/arm)

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_formations_catalog.py \
  tests/test_world_stats.py \
  -q
```
