# WO-EXPLORE-STATUS-LIVE-COUNTERS — explore status must report mid-run progress

**Status:** OPEN · EXECUTE · MED · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28T02:52Z bank · EXEC seeded overnight after #142+#143  
**Refs:** wire-class W8 · overnight carte blanche

## Goal
`explore status` must expose live counters mid-run — never silent zeros that look idle.

## Accept
1. Active run → non-zero progress or honest unavailable/pending.
2. Pin: mid-run vs completed vs idle distinguishable.
3. Suite + STATUS. live-prove safe half OK; turn-spend NOT-ATTEMPTED.

## Constraints
No new CLI verbs. No formations/chains (#144 CC). Explicit paths only.
