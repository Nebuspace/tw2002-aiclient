# WO-CLEANUP-COACHING-STRATEGIES-JSON-UNREACHABLE-CARD

**Status:** IN FLIGHT
**Priority:** LOW
**Gated:** no

## Goal

Make `planet_production` self-documenting as unreachable: no live tip path emits
`when_trigger=planet_management`. Mark the card; do not invent a genesis trigger
producer this pass.

## Scope

- `data/coach/strategies.json`
- This WO file

## Accept

1. `planet_production` carries `status: "unreachable"` (+ short note).
2. `load_coach_kb` / existing coach tests still green (extra keys ignored).
3. live-prove: n/a (data honesty; no live path).
