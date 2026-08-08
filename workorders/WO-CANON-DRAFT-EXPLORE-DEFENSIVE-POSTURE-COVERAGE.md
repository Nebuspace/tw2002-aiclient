# WO-CANON-DRAFT-EXPLORE-DEFENSIVE-POSTURE-COVERAGE

**Goal:** `session/explore_defensive_posture.py` is live-wired into
`explore.py`/`priority_engine.py`/`world_model.py` with zero canon coverage
anywhere. The module's own docstring flags its policy constants as "judgment,
documented — escalate only if Max wants different defaults," i.e. it expected
canon documentation that never followed.

**Scope:**
- Draft a canon/strategy/ entry (or alongside sibling explore decision modules
  like reroute_vs_fight) documenting the module's identity + its 5 policy
  constants as judgment calls, not ratified numbers:
  - FIGHTER_FLOOR=20
  - CREDIT_FRACTION_CEILING=10%
  - FIGHTER_UNIT_PRICE_DEFAULT=100cr
  - DEALER_DETOUR_TURN_CEILING=20 turns
  - CASH_FLOOR_AFTER=10000cr
- Docs-only; do not touch the module's code or constants.

**Accept:**
- Canon entry exists, cites file:line for each constant, frames them as
  judgment defaults not ratified numbers.

**Refs:** 6-lens aiclient audit 2026-08-08T02:12Z; session/explore_defensive_posture.py
