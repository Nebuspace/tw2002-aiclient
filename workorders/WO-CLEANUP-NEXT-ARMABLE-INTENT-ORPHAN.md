# WO-CLEANUP-NEXT-ARMABLE-INTENT-ORPHAN

**Status:** OPEN (in PR)  
**Priority:** MED (slice of WO-CLEANUP-DEAD-SYMBOLS-BATCH-2026-08-05)  
**Claimed-by:** impl-aiclient-cursor  

## Goal

Retire `explore.next_armable_intent` — zero product callers; Play E-cycle retired (#247).

## Tip-verify

| Check | Result |
|---|---|
| Product callers | **0** (only tests) |
| Play arm path | `app.py` uses find-stardock toggle → `INTENT_FIND_STARDOCK` / `INTENT_MAP_FILL` |
| `ARMABLE_INTENTS` | Still the documented 2-wide Play set (formations catalog tests pin it) — **keep** |

## Diff

- Remove `next_armable_intent` from `explore.py`; note retirement in comment
- Drop dedicated test; assert symbol absent in ARMABLE_INTENTS pin test

## Accept

- [ ] Symbol gone; `ARMABLE_INTENTS` retained
- [ ] `tests/test_play_explore_intents.py` + formations catalog pin green

## live-prove

`n/a` — dead-helper retirement.
