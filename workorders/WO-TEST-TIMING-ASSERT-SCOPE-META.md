# WO-TEST-TIMING-ASSERT-SCOPE-META

**Goal:** Cheap mechanical approximate gate for the **scope** half of the timing-assert convention (prose landed in #185): flag rusage/CPU budget asserts whose measured value derives from a **process the test itself spawned** — whole-life by construction, the #184 shape.

**Context:** Order is AST-enforced (`test_timing_assert_order.py`). Scope is doc-only (#185). CC offer: a full semantic scope detector is hard; an approximate version — “CPU/rusage assert over a child the test spawned” — would have caught #184. Hub GO after #185 merge.

**Scope:**
- Prefer extending `tests/test_timing_assert_order.py` **or** a sibling meta-test module — keep allowlist+reason pattern.
- Do **not** rewrite product code or widen thresholds.
- Falsify: feed a synthetic #184-shaped pin → RED; a residual-stamped pin → green; a genuine order inversion still caught by the order gate.

**Accept:**
1. Meta-test (or extension) reddens on whole-life rusage/CPU asserts over test-spawned children (documented heuristic).
2. Current suite green under it (or allowlist with reason).
3. Docstring points at #185 scope prose + #184 exemplar.
4. live-prove `n/a`.

**Proof:** injection RED/GREEN + suite CI.

**Refs:** #185 · #184 · CC STATUS 19:43:52Z offer.
