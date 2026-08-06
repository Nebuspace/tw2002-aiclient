# WO-CLEANUP-STRIP-DUPLICATE-COMPOSER — retire string-only from_row helper

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-STRIP-DUPLICATE-COMPOSER`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Remove `compose_profile_strip_from_row` — zero product callers (`screens.py` uses
`compose_profile_strip_segments_from_row` only). Keep host-fallback coverage by
porting its tests onto the segmented sibling.

## Accept

1. `compose_profile_strip_from_row` deleted.
2. Tests green against `compose_profile_strip_segments_from_row`.
3. live-prove `n/a` (dead-API cleanup).

## Refs

- Cycle-43 · `cockpit/strip.py` · `tests/test_cockpit_strip.py`
