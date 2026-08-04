# WO-AUDIT-CANON-DRAFT-EXPLORE-FLAGS-ASYMMETRY

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** MED
**Depends-on:** none
**Gated:** no — canon fold-in only

## Goal

Pin Play explore flag asymmetry (`dock_new_ports` default ON / `fight_tolls` OFF;
un-coerced `fight_tolls` payload) in canon so a future "tidy" does not symmetrize them.

## Approach

Primary home: [exploration-policy](../canon/strategy/exploration-policy.md). Pointer from
[mode-line](../canon/surfaces/mode-line-and-teach-controls.md) Explore/`P` split.

## Scope

- `canon/strategy/exploration-policy.md`
- `canon/surfaces/mode-line-and-teach-controls.md` (one-line cross-ref)
- This WO file

## Accept

1. Canon names both flags, Play defaults, and the `bool` vs un-coerced asymmetry + rationale.
2. Explicit "must not be tidied into symmetry."
3. live-prove: `n/a` (docs-only).

## Proof

`rg explore_flags|fight_tolls|dock_new_ports canon/strategy/exploration-policy.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-EXPLORE-FLAGS-ASYMMETRY`
- `tw2002_aiclient/cockpit/explore_flags.py`
