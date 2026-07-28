# WO-BADGE-SCAN-IDENTITY-FLOOR

**Goal:** Replace the vacuous cardinality positive-control in `tests/test_mode_badge_vocabulary.py` (`assert len(py_files) > 10`) with **identity** — at least one representative path per product subpackage must appear in the scanned set.

**Context (CC non-temporal audit spill, 2026-07-28):** Dropping an entire subpackage still leaves 59–80 `.py` files; `> 10` always passes. Realistic failure (walk stops descending into one package) stays green. Exemplar already in-tree: `tests/test_status_vocabulary_guard.py` asserts specific expected paths, not a count.

**Scope:**
- `tests/test_mode_badge_vocabulary.py` (control only)
- Optionally mirror the status-vocab pattern; do not change product badge logic

**Accept:**
1. Cardinality-only floor gone (or demoted to defence-in-depth behind identity).
2. Assert presence of ≥1 representative file per subpackage that the gate is meant to cover (`cockpit/`, `session/`, root, `menu/`, `loops/` — match whatever the walk actually claims).
3. Falsify: remove/rename one representative from the discovered set (or inject a narrowed walk) → RED; restore → GREEN.
4. Suite green. live-prove `n/a`.

**Proof:** injection matrix + suite CI.

**Refs:** CC 19:32:59Z · `test_status_vocabulary_guard.py` identity control.
