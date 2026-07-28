# WO-CHAIN-K9-BUDGET-ASSERT — Assert step budget + note, not wall-clock

**Status:** BANKED · MED · CC heritage (#127)  
**Posted:** 2026-07-28T02:02Z · hub (from CC #128 mid-STATUS)  
**Seat:** impl-claudecode-aiclient (preferred)  
**Depends:** after #128 Accept preferred (do not widen #128)

## Goal

`test_complete_k9_terminates_under_a_second_with_a_truncation_note` asserts
`elapsed < 1.0` **before** `assert note is not None`. Wall-clock is a machine
property; the real #127 deliverable is the deterministic step budget +
truncation note. Timing slips fail the test with a timing message and **mask**
the correctness check. Serial repro ~1/3 at ~1.019s confirms it is not merely
parallel load.

Same family: `test_ring_5000_and_50000_return_normally_without_recursion_error`
(`< 5.0`) — better ordered, still machine-dependent.

## Accept

1. Primary asserts: step budget / truncation `note` (deterministic).
2. Any wall-clock canary is **last**, generous headroom, cannot mask correctness.
3. Suite green; no new flakes of this class on K9 under serial or `-n auto`.

## Refs

- CC STATUS 2026-07-28T02:01:00Z
- #127 `WO-CHAIN-SEARCH-BUDGET`
