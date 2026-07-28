# WO-TEST-TIMING-ASSERT-ORDER — AST meta-test: no wall-clock assert before correctness

**Status:** OPEN · EXECUTE · LOW · Cursor-class · impl-aiclient-cursor · IDLE-KICK feed  
**Posted:** 2026-07-28T03:32Z · hub (CC offer after #134)  
**Refs:** CC STATUS #134 2026-07-28T03:31:18Z

## Goal
Structurally prevent a 4th twin of the K9 defect: in any test function, no `assert` on a
`perf_counter` (or wall-clock) delta may precede a non-timing assert.

## Accept
1. AST (or similar) meta-test fails when wall-clock assert precedes non-timing assert in same function.
2. Current suite green under the meta-test (or documented allowlist with reason).
3. Suite + STATUS; live-prove n/a.

## Constraints
Do not ban CPU/rusage canaries that correctly follow behavioural asserts. Optional — build when free.
