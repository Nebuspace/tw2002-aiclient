# WO-CLEANUP-FIGHTER-TOLL-DEAD-ALLOW-PAY-PARAM — drop dead allow_pay kwarg

**Status:** DONE · tip fighter_toll_policy has no allow_pay parameter
**Posted:** queue-aiclient.md (ungated MED)

## Goal

Remove documentation-only `allow_pay` from `decide_encounter` — it never
changed behavior and implied a mute switch for never-auto-Pay. Keep the
structural never-`P` pin + test.

## Accept

1. `allow_pay` gone from signature/call sites/tests.
2. `test_pay_is_never_selected_even_when_the_key_is_offered` still green.
3. Canon one-liners no longer describe a live `allow_pay` kwarg.
4. live-prove `n/a` (policy API cleanup; never-auto-Pay unchanged).

## Refs

- `session/fighter_toll_policy.py::decide_encounter`
- `tests/test_fighter_toll_policy.py`
