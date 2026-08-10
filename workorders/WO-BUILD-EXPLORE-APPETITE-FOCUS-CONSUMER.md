# WO-BUILD-EXPLORE-APPETITE-FOCUS-CONSUMER

**Status:** OPEN → this PR
**Seat:** `impl-aiclient-cursor`
**Priority:** MED
**Gated:** no (ranking/suggestion only; no arm/send; affordability thresholds stay Pending)
**Depends:** tip `explore_appetite_raised` writer (`chain_depletion` / `chain_status`); canon draft #639
**Refs:** `canon/strategy/exploration-policy.md` § Explore / exploit appetite ·
`canon/engine/priority-engine.md` § FOCUS ranking input — affordability ·
`PENDING-AFFORDABILITY-EXPLORE-WEIGHT-DEFINITION`

## Goal

Wire the already-written `explore_appetite_raised` status flag into
`focus_status.recommend_focus_candidates` so depletion raises the explore
FOCUS overlay weight. Do **not** invent affordability credit thresholds.

## Scope

1. `tw2002_aiclient/focus_status.py` — read `EXPLORE_APPETITE_RAISED_KEY`; raise explore
   `overlay_weight` via `WEIGHT_EXPLORE_APPETITE`.
2. `tests/test_focus_status.py` — pin depleting-chain explore boost + omit-until-known.
3. Canon tip-honesty: exploration-policy.md + priority-engine.md (zero-readers → LIVE).
4. This WO file.

## Constraints

- Suggestion / ranking only — never arm explore, never rotate a running loop, never send.
- Affordability OR-cause of the same flag stays Pending — no credit≥quote inventing.
- Explicit-path commits; no secrets; no operator-home paths.

## Accept

1. `explore_appetite_raised=True` + executable chain + met catalog prereqs → explore sorts
   above `run_chain` with `priority_weight == WEIGHT_EXPLORE_APPETITE`.
2. Flag absent/false → no invented explore overlay boost.
3. Canon no longer claims zero product readers for the flag.
4. live-prove: `n/a` (offline FOCUS ranking; no TWGS arm).

## Proof

```
.venv/bin/python -m pytest -n0 tests/test_focus_status.py -q --tb=short
```
