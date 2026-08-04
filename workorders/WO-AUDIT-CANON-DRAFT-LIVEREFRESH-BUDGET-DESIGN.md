# WO-AUDIT-CANON-DRAFT-LIVEREFRESH-BUDGET-DESIGN

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** LOW
**Depends-on:** none
**Gated:** no

## Goal

Canon-home for `live_refresh.py`: budget-not-throttle idle-tick design + measured
cost rationale + self-retirement of automatic chain recompute.

## Scope

- `canon/surfaces/trainer-cockpit.md` (HUD section + citations)
- This WO file

## Accept

1. Canon names intervals, `CHAIN_BUDGET_S`, session retirement, keep-previous honesty.
2. States why throttle alone is the wrong instrument (measured cost table cited in tip module).
3. live-prove: `n/a` (docs-only).

## Proof

`rg live_refresh|CHAIN_BUDGET canon/surfaces/trainer-cockpit.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-LIVEREFRESH-BUDGET-DESIGN`
- `tw2002_aiclient/cockpit/live_refresh.py`
