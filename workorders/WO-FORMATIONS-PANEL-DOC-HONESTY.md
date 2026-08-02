# WO-FORMATIONS-PANEL-DOC-HONESTY — Scroll-Law doc refresh for FORMATIONS panel

**Status:** OPEN · seat `impl-aiclient-cursor` (self-direct, hub authorized 2026-08-02T23:20:30Z)  
**Branch:** `wo/FORMATIONS-PANEL-DOC-HONESTY`  
**Depends:** `main` ≥ `1c5996a` (#317 FORMATIONS panel · #320 catalog port)  
**Refs:** `cockpit/formations.py` · `world_stats.py` · `formations.catalog_world` · `test_status_vocabulary_guard.py`

## Goal

Rewrite stale FORMATIONS panel documentation to match shipped producers (#317/#320). No behavior change.

## Scope

1. Fix `tw2002_aiclient/cockpit/formations.py` module docstring: stop claiming daemon status lacks `formations_panel` or that WO-FORMATIONS-CATALOG-PORT is still pending.
2. Fix stale "no producer yet" comments in `tests/test_cockpit_fold.py` that contradict `world_stats.WorldStats` wiring.
3. This WO file.

## Out of scope

- ARMABLE_INTENTS / Play E-cycle expansion (#247 stays 2-wide).
- Canon prose edits (Max-gated).
- STARVED_ALLOWLIST changes (`formations_panel` / `formations_count` already removed on main).

## Accept

1. Module docstring accurately names `world_stats` producer and in-tree `catalog_world` explore path.
2. No false "awaiting WO-FORMATIONS-CATALOG-PORT" claims remain in scoped files.
3. Suite green on formations panel / status vocabulary pins.

## Proof

`.venv/bin/python -m pytest tests/test_cockpit_fold.py tests/test_status_vocabulary_guard.py tests/test_world_stats.py -q`
