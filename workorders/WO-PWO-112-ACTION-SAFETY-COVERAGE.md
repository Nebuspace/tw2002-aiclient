# WO-PWO-112-ACTION-SAFETY-COVERAGE — proven action-safety coverage map

> Status: **DONE** · origin `528252a` (#348) · seat `impl-aiclient-cursor` · Accept 2026-08-03  
> Type: harden · PWO-112  
> Tip base: `e065ffa` → merged `528252a`

## Goal
Close PWO-112 Accept residual: **one proven coverage map** of action-safety byte guards (canon ladder → source marker + unit proof), without claiming DONE on scattered guards alone.

## Scope
- A: `tw2002_aiclient/action_safety.py` (coverage inventory)
- B: `tests/test_action_safety_coverage.py` (map intact + unit-per-class)
- C: ULTRACODE + P9 PREP tip → LIVE
- D: this WO file

## Constraints
- Not a rewrite of all guards into one runtime module
- Do not conflate with PWO-113 (alignment) beyond referencing its pin in the map
- No live arm / money-path prove

## Accept
1. Coverage map lists canon ladder classes with source + proof pins
2. `assert_coverage_map_intact` + parametrized unit-per-class green
3. NEVER_AUTO depth audit still referenced (not replaced)

## Proof
`pytest tests/test_action_safety_coverage.py` · CI suite · live-prove n/a (offline coverage map)
