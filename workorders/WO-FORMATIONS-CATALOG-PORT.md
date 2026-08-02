# WO-FORMATIONS-CATALOG-PORT — Port formations catalogue into tw2002_aiclient

**Status:** READY · EXECUTE · HIGH · Claude Code · Play-visible  
**Seat:** `impl-claudecode-aiclient`  
**Branch:** `wo/FORMATIONS-CATALOG-PORT`  
**Posted:** 2026-07-28T04:41Z · hub re-armed 2026-08-02 after #316  
**Refs:** ADR-001 deleted twclient · #142 catalog_provider seam · archive `formations.py`

## Why

`plan_find_formations()` still takes `catalog_provider=None` and returns `mode="unavailable"`.
Cockpit FORMATIONS panel + GOALS `formations_count` / `genesis_count` stay honest-empty until
a real in-tree provider exists. Archive source: `archive/pre-rebirth-2026-07-23/code/twclient/formations.py`
(pure topology over world_model — locate/recommend only, never deploys Genesis).

## Goal

Port a real formations catalogue into `tw2002_aiclient/` (no twclient resurrect). Wire it as
`catalog_provider` for `explore.plan_find_formations()` and populate status
`formations_panel` / `formations_count` / `genesis_count`.

## Scope

1. In-tree provider module (port/adapt archive detector; ADR-001 — no `twclient` import).
2. Wire call site(s) so product paths get a provider (not test-only).
3. Populate daemon/status fields the cockpit already reads.
4. Pins: provider + unavailable path; suite green.
5. This WO file Status → cite tip on DONE.

## Out of scope

- Deploying Genesis / unguarded auto-fire money path
- Full explore automaton redesign
- Banner-stamp hygiene (separate Cursor WO)

## Accept

1. In-tree provider exercised by tests; `plan_find_formations` no longer unconditional `unavailable` when world has data.
2. Status/panel scalars populated from a real world-model scan (or documented honest empty when none).
3. No `twclient` resurrect. Suite green. Live: DEFERRED → Cursor after merge (or safe read-only probe).

## Constraints

No stub that only greens imports. LOCATE/CATALOG/RECOMMEND only — never deploy Genesis from this WO.
Money-path adjacent disclosure OK in STATUS; not a Max-gate for locate-only.

## Proof

```bash
.venv/bin/python -m pytest -q  # or focused formations/explore/cockpit pins named in STATUS
```
