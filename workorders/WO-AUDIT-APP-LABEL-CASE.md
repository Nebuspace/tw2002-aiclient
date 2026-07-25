# WO-AUDIT-APP-LABEL-CASE — Canon “App” vs shipped `APP`

> Status: **DRAFT** 2026-07-25 · AUDIT-OKF-6LENS · Priority: P2 · Lens: L2  
> Type: polish · Refs: `control_seat.APP_LABEL` · `mode-line-and-teach-controls.md`

## Goal
Resolve display-string tension: canon short label **App** vs tip chip text `APP` — either update canon to match shipped uppercase chip, or change label + tests to Title case.

## Scope
- A: Hub/Max one-line ruling (canon vs code)
- B: Single-file label + matrix tests OR canon prose — not both without ruling
- C: visual-language / mode-line tip notes

## Constraints
No seat-key changes. Vocabulary gate must stay clean. Prefer docs-win if Max silent → update canon to `APP` as shipped (smallest product risk).

## Accept
One spelling in canon + product tip; tests/matrix updated if code changes.

## Proof
`rg APP_LABEL` + chip matrix · docs or product commit. Push waits Accept.

## Refs
`control_seat.py` `APP_LABEL = "APP"` · OKF-060 tip-stamp
