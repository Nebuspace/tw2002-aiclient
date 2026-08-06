# WO-CLEANUP-ACTION-SAFETY-COVERAGE-IDS-ORPHAN — drop unused coverage_ids()

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-ACTION-SAFETY-COVERAGE-IDS-ORPHAN`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Remove `action_safety.coverage_ids()` — zero callers (product or test).
Uniqueness stays covered by `assert_coverage_map_intact` + the
`all_coverage()`-based uniqueness test.

## Accept

1. `coverage_ids` gone from tip.
2. `tests/test_action_safety_coverage.py` still green.
3. live-prove `n/a` (dead API).

## Refs

- `action_safety.py` · `tests/test_action_safety_coverage.py`
