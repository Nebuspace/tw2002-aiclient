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

---

## Companion rule — SCOPE (added by `WO-TEST-TIMING-ASSERT-SCOPE`, 2026-07-28)

Order is enforced by `tests/test_timing_assert_order.py`. **Scope is not enforced, and is
the other half of the rule:**

> **A timing or budget assertion measures only the window its message names.** If setup,
> teardown, or unrelated work sits inside the bracket, **split the measurement** — self-stamp
> a baseline, or time the call alone — rather than widening the threshold. **Size the bound
> against the worst condition the suite actually runs in**, not a quiet box.

**Why it needed writing down.** The Constraints line above deliberately exempts CPU/rusage
canaries that follow behavioural asserts — correct, because those are forced data
dependencies rather than masking. But that exemption is precisely where the ordering gate
stops looking, and the class it waves through is the one that produced #184. **A green order
check is not evidence of a sound budget.**

**Exemplar — `WO-DEAD-TERMINAL-SPIN-INTERMITTENT` (#184).** `assert cpu_s < 0.5,
"consumed …s CPU exiting — looks like it spun first"` was order-correct (`assert exited` ran
first) and still wrong: `cpu_s` was the child's **whole-life** rusage — interpreter start,
imports, curses init, first render — while the message charged the exit path. Setup measured
**82–84%** of that number. It went red at 0.539s *with `exited` passing*, accusing the code of
a spin that had not happened.

The repair is the pattern to copy: the child stamps its own `getrusage(RUSAGE_SELF)` when it
first blocks in the loop under test; the assertion reads only the residual after that.
Detection got **stronger** — an injected 0.4s spin reddens now, where the whole-life pin buried
a spin that size in its own startup noise. A missing stamp **fails**; it never falls back to the
whole-life number, because that fallback would restore the defect while still reporting green.

Full prose lives in the `tests/test_timing_assert_order.py` module docstring, next to the
enforcement, so it is read when the gate fires.
