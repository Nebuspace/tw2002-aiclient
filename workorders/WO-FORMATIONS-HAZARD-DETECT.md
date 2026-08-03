# WO-FORMATIONS-HAZARD-DETECT — One-way + warp-sink catalogue

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T00:37:00Z  
**Branch:** `wo/FORMATIONS-HAZARD-DETECT`  
**Zone:** `tw2002-aiclient` only  
**Refs:** #324 deferred hazards · archive `_one_ways`/`_warp_sinks` · `canon/strategy/special-formations.md`

## Goal

Catalogue **one-way warps** and **warp sinks** in the shared detector so the
FORMATIONS panel can show route hazards. They are **not** genesis candidates
(`formations_count` may exceed `genesis_count`).

## Scope

- `tw2002_aiclient/formations.py` — port `_one_ways` / `_warp_sinks` / helpers
- `tests/` — archive fixtures adapted
- `workorders/WO-FORMATIONS-HAZARD-DETECT.md` — this file

## Constraints

- No guard wiring / STOP escalation this WO (catalogue + panel only)
- No Play E-cycle / ARMABLE widen (#247)
- Snake_case kinds (`one_way`, `warp_sink`)
- Explicit paths — never `git add -A`

## Accept

1. Archive one-way + warp-sink fixtures catalogue as expected
2. Hazards absent from `genesis_candidates`; present in panel
3. Dead-end / bubble behaviour unchanged on prior fixtures
4. Focused tests green; live `n/a`

## Proof

```bash
.venv/bin/python -m pytest -n0 \
  tests/test_formations_catalog.py \
  tests/test_world_stats.py \
  -q
```
