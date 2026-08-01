# WO-RETIRE-EXPLORE-OFFER

**Status:** READY · EXECUTE · MED · Play honesty · Cursor  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/RETIRE-EXPLORE-OFFER`  
**Depends:** `main` ≥ `1df5ab2` (#303 help vocab)

## Why

Max ruled Offer off the calm strip and **no explore-offer copy in LOGS**. `compose_explore_offer` in `cockpit/explore_flags.py` is **test-only** (unused-code tick WIRE→tip-check = RETIRE). Leaving it invites re-wiring the wrong affordance.

## Goal

**RETIRE** `compose_explore_offer` (and its dedicated test pins). Keep explore classification / flag helpers that still feed App-armed policy.

## Scope

1. Delete `compose_explore_offer` from `tw2002_aiclient/cockpit/explore_flags.py` (and any `__all__` / docstring that advertises it).
2. Remove or rewrite `tests/test_play_explore_flags.py` pins that only exist for that helper.
3. Do **not** reintroduce Offer?/confirm-gate teach copy. `HOLD_TOKEN`/`OFFER_TOKEN` may stay as “not on TEACH_TOKENS” negative pins unless trivial to keep.
4. This WO on the branch.

## Out of scope

`compose_arm_chip` retire · formations catalog · money-path start verbs · #283.

## Accept

1. No product or test caller of `compose_explore_offer`.
2. Focused explore_flags + related pins green; full `pytest tests/` green.
3. Live-prove **n/a** (retire dead helper).

## Proof

pytest + STATUS. No self-merge.

## Refs

unused-code tick · Max strip rulings · `#303` calm help
