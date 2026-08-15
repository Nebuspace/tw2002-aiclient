# WO-ESCALATE-PORT-FLOOR-TRADED-SINCE-PRIOR-UNREACHABLE

**Status:** resolve as accept-dark (hub pushback on #715)  
**Branch:** `wo/ESCALATE-PORT-FLOOR-TRADED-SINCE-PRIOR`  
**Seat:** impl-aiclient-h1

## Goal

Close the READY-row either/or — wire a `traded_since_prior` signal **or** accept that regrowth
estimation stays dark on tip product paths — by ruling **accept-dark**.

## Why not wire

No tip ledger knows whether this profile traded the port since the prior observation. Inventing
`False`/`True` in `world_model._record_port_floor_observation` would fake regrowth windows.
Related hold (`DECISION-PORT-FLOOR-CAPTURE-HOLD-RATIONALE`) already keeps the module analysis-only.

## Deliverable

- `DECISION-PORT-FLOOR-TRADED-SINCE-PRIOR-ACCEPT-DARK` in `canon/DECISIONS.md` (Ruled).
- Tip-honest docstring / port-economics cites naming the decision (not an open escalate).
- No product behavior change; no fabricated flag.

## Accept

- DECISIONS entry Status is Ruled accept-dark; either/or is closed.
- Product capture path still leaves `traded_since_prior` unknown.
- Docs cite the decision id, not an open WO escalate as the standing state.

## Proof

- Docs + docstring only → live-prove `n/a`.
- `rg traded_since_prior tw2002_aiclient/world_model.py` still shows unknown-by-decision, no invented bool.
