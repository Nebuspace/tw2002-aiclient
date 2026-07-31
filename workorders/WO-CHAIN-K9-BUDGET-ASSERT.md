# WO-CHAIN-K9-BUDGET-ASSERT — Assert step budget + note, not wall-clock

**Status:** DONE · origin `9833550` (#134) · tip-honesty stamp 2026-07-31 (note-before-canary / `_BUDGET_CANARY_S` on main; banner was stale OPEN)
**Posted:** 2026-07-28T02:02Z · hub (from CC #128 mid-STATUS) · EXEC 2026-07-28T03:07Z  
**Seat:** impl-claudecode-aiclient  
**Depends:** #128 MERGED (`c56f852`)

## Goal

Wall-clock budget asserts are machine properties that **mask** correctness checks
when ordered first. Fix the class, not one test.

Known sites (CC characterisation):
1. `test_complete_k9_terminates_under_a_second_with_a_truncation_note` — `elapsed < 1.0` **before** `note is not None`
2. Two `test_dead_terminal_spin.py` PTY-timing twins (same load-sensitive family)
3. Related: `test_ring_5000_and_50000_return_normally_without_recursion_error` (`< 5.0`) — better ordered, still machine-dependent

## Accept

1. Primary asserts: step budget / truncation `note` / behavioural outcome (deterministic).
2. Any wall-clock canary is **last**, generous headroom, cannot mask correctness.
3. Cover all three characterised sites (K9 + two dead-terminal PTY); ring-5k/50k if touched in same file pass.
4. Suite green; no new flakes of this class on K9 under serial or `-n auto`.
5. live-prove n/a (offline tests).

## Refs

- CC STATUS 2026-07-28T02:01:00Z · 02:51:51Z widen · 03:02:22Z ready for #134
- #127 `WO-CHAIN-SEARCH-BUDGET`
