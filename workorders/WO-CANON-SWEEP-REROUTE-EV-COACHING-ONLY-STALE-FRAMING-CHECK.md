# WO-CANON-SWEEP-REROUTE-EV-COACHING-ONLY-STALE-FRAMING-CHECK

**Status:** DONE (verified clean — no stale coaching-only ceiling in the six citing docs)
**Priority:** LOW
**Gated:** no

## Goal

Confirm none of the six docs that cited the 2026-08-05 reroute-vs-fight-EV ruling still assert
the superseded **"coaching-only, never auto-firing"** design ceiling after DECISIONS.md's same-day
correction.

## Verify-first (2026-08-06 tip `d91c2f2`)

Searched for `coaching-only` / `never auto-fir` / related ceilings in:

| Doc | Result |
|---|---|
| `canon/architecture/app-autopilot-model.md` | clean |
| `canon/engine/priority-engine.md` | clean (coaching cross-link only) |
| `canon/strategy/exploration-policy.md` | clean |
| `canon/engine/candidate-mining.md` | clean (`never fire unverified` = safety, not coaching ceiling) |
| `canon/doctrine/action-safety-guards.md` | clean (same; `CYCLES_HARD_CEILING` ≠ coaching-only) |
| `canon/engine/screen-understanding.md` | clean |

Superseding prose lives only in `canon/DECISIONS.md` § six-archived-modules-reroute-vs-fight-ev
(correction block). No doc edits required this pass.

## Accept

1. WO records the verify-first table above.
2. live-prove: n/a (docs verify / tip-close).
