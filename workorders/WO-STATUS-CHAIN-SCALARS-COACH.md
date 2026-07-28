# WO-STATUS-CHAIN-SCALARS-COACH — chain scalars on status + coach wire

**Status:** DONE · origin `5f35188` (#162) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28T13:21Z · hub (CC scoping 12:55Z · ruling 12:56Z)  
**Supersedes:** narrow `WO-COACH-CHAIN-TRIGGER` / #159 until this lands  
**Depends:** #161 `WO-COACH-ENGINE-PORT` on `main` · #147 chains surface

## Goal

Expose discovered-chain **scalars** on the cockpit `status` dict and wire the coaching-engine path so GOALS Chain row and coach `chain_opportunity` can fire without inventing formatters or dragging `chain_search` onto the hot redraw path.

## Scope

- **`app.py`:** merge `chain_hops` + `chain_unit` into status via `chain_units.chain_hop_count_and_unit(discovered)`; **memoised / on-demand** (existing chains-popup recompute path OK) — **not per-tick `recompute()`**
- **`decisions.py`:** read scalars; defensive one-shot `load_coach_kb` — **never raises** (placeholder on failure)
- Pins: `tests/test_dead_terminal_spin.py` CPU budget still green; GOALS not permanently "unknown"; coach fires on discovered shape when data present

## Out of scope

- Daemon / `session/protocol.py` changes (discovery is client-side)
- DEPLOY-WINDOW
- Micro step12 · ignore-list rehab

## Accept

1. Status carries honest `chain_hops` / `chain_unit` when discovery has run; absent/unknown when not.
2. Coach path uses `infer_coach_triggers` + `compose_decisions_coach` + tip `data/coach/*` only.
3. Suite + STATUS; live-prove `n/a` unless DECISIONS paint is live-touching.

## Refs

- CC DECISION 12:53–12:55Z · hub 12:54–12:56Z
