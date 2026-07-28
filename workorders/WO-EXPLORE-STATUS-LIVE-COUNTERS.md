# WO-EXPLORE-STATUS-LIVE-COUNTERS — explore status must report mid-run progress

**Status:** BANKED · MED · Cursor-class OK  
**Posted:** 2026-07-28T02:52Z · hub bank from #128 live-prove (CC)  
**Refs:** CC DECISION-NEEDED 2026-07-28T02:51:51Z

## Goal
`explore status` (and any Play mirror) must expose live counters while a run is in flight — not only at completion.

## Observed defect
Mid-run polls showed `distinct_sectors=0 · sends_issued=0 · turns_remaining=40` while the viewport was flying (1→5→18258). Post-completion polls showed the true totals. Operators conclude "stuck" incorrectly.

## Accept
1. During an active explore run, status returns non-zero progress fields that match observed motion (or an honest "unavailable" with reason — not silent zeros that look like idle).
2. Pin: mid-run vs completed shapes distinguishable; zeros only when truly idle/not started.
3. Suite + STATUS; live-prove n/a unless easy.

## Constraints
Do not invent new CLI verbs. Do not widen #128.
