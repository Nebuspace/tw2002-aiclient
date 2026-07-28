# WO-TEST-TIMING-ASSERT-SCOPE

**Goal:** Extend the timing-assert convention (order already covered by `WO-TEST-TIMING-ASSERT-ORDER` / `tests/test_timing_assert_order.py`) with a **scope** clause so #184 cannot recur by review silence.

**Context (CC budget-window audit 2026-07-28):** No new #184-shaped defects in the tree. Existing sites bracket only the operation. Clock-bomb shape structurally impossible (no `datetime.now` in tests). Gap: order rule is enforced; **scope** ("measure only the window the message names") is not written down — #184 obeyed order and still shipped a whole-life rusage pin sold as "CPU exiting."

**Scope (owned paths):**
- `workorders/WO-TEST-TIMING-ASSERT-ORDER.md` (add scope section) **and/or**
- `tests/test_timing_assert_order.py` module docstring (canonical in-tree reminder)
- Optional: one-line cross-ref from a nearby test canary comment template — do **not** invent a new AST meta-test unless trivial and falsifiable

**Constraints:**
- Doc/convention only unless a tiny meta-test is clearly load-bearing.
- Do not widen existing timing thresholds "to fix" scope — split the measurement instead.
- Non-temporal thresholds (counts/sizes/ratios) are **out of scope** (separate pass if wanted).
- live-prove `n/a`.

**Accept:**
1. Written scope rule ≈: *a timing/budget assertion measures only the window its message names; if setup/teardown/unrelated work sits inside the bracket, split (self-stamp or time the call alone) rather than widen the threshold; size the bound against the worst condition the suite actually runs in, not a quiet box.*
2. Points at #184 / residual-stamp pattern as the exemplar.
3. Suite green (no behaviour change expected).

**Proof:** STATUS quotes the landed prose; suite CI.

**Refs:** #184 · CC audit 19:28:37Z · `WO-TEST-TIMING-ASSERT-ORDER`.
