# WO-STOPBANNER-ROUTE-HAZARD-LABEL — Catalog + banner label for route_hazard

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct)  
**Posted:** 2026-08-03T01:35:00Z  
**Branch:** `wo/STOPBANNER-ROUTE-HAZARD-LABEL`  
**Zone:** `tw2002-aiclient` only  
**Refs:** hub GO 03:13Z · #327–#329 · `control-and-escalation.md` open-by-construction

## Goal

Record shipped `route_hazard` STOPs in the escalation catalog and STOP-banner
label map so `route_hazard:one_way:A->B` renders `route hazard: one_way:A->B`.

## Scope

- `canon/architecture/control-and-escalation.md` — catalog row
- `tw2002_aiclient/cockpit/stopbanner.py` — `INTERVENTION_REASON_LABELS`
- `tests/test_cockpit_stopbanner.py` — CANON_CATALOG + qualified pin
- `canon/strategy/special-formations.md` — close "Still open" note
- `workorders/WO-STOPBANNER-ROUTE-HAZARD-LABEL.md` — this file

## Accept

1. Catalog row + label map agree (`route_hazard` → `route hazard`)
2. Qualified code renders label + detail
3. Focused stopbanner tests green; live `n/a`

## Proof

```bash
.venv/bin/python -m pytest -n0 tests/test_cockpit_stopbanner.py -q
```
