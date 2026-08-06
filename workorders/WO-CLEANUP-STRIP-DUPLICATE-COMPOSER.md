# WO-CLEANUP-STRIP-DUPLICATE-COMPOSER — retire string-only from_row helper

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-STRIP-DUPLICATE-COMPOSER`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Retire **product** use of `compose_profile_strip_from_row` — zero live product
callers (`screens.py` uses `compose_profile_strip_segments_from_row` only).

**REVISE (hub REJECT #481):** do **not** delete the symbol — keep a thin
deprecated shim so pinned historical `screens.py` blobs in
`tests/test_safe_addstr_choke.py` still import against current `strip.py`.
Port dedicated tests onto the segmented sibling.

## Accept

1. No product callers of the string-only helper (shim may remain for test-blob import compat).
2. Host-fallback coverage lives on `compose_profile_strip_segments_from_row` tests.
3. `tests/test_safe_addstr_choke.py` + `tests/test_cockpit_strip.py` green.
4. live-prove `n/a` (API hygiene).

## Refs

- Cycle-43 · `cockpit/strip.py` · `tests/test_cockpit_strip.py`
