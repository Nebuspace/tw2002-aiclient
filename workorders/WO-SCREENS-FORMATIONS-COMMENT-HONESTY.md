# WO-SCREENS-FORMATIONS-COMMENT-HONESTY — Fix stale FORMATIONS draw comment in screens.py

**Status:** OPEN · seat `impl-aiclient-cursor` (self-claim, hub authorized continuous self-direct)  
**Branch:** `wo/SCREENS-FORMATIONS-COMMENT-HONESTY`  
**Depends:** `main` ≥ `02a3f7f` (#317 catalog port · #321 panel doc honesty)  
**Refs:** `tw2002_aiclient/screens.py` ~1691–1696 · `world_stats.py` · `cockpit/formations.py`

## Goal

Update the stale FORMATIONS panel draw-path comment in `screens.py` that still claims a later WO must wire a real catalog. No behavior change.

## Scope

1. Fix comment at `tw2002_aiclient/screens.py` ~1694–1696: name `world_stats.WorldStats` as the `formations_panel` producer and note catalog wiring landed in #317/#321.
2. This WO file.

## Out of scope

- Behavior, layout, or producer changes.
- Other doc/comment sweeps (see WO-FORMATIONS-PANEL-DOC-HONESTY on main).

## Accept

1. Comment accurately states `formations_panel` is produced on daemon status and rendered via `compose_formations_panel`.
2. No false "awaiting later WO" claim remains at the scoped lines.
3. Optional cheap pytest pin if convenient.

## Proof

```bash
# comment-only — optional spot check:
.venv/bin/python -m pytest tests/test_cockpit_fold.py -q -k formations
```
