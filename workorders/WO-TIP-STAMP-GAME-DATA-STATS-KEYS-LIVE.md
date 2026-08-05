# WO-TIP-STAMP-GAME-DATA-STATS-KEYS-LIVE

**Status:** DONE (pending merge) · tip-stamp / false-positive correction
**Priority:** LOW
**Gated:** no

## Goal

Close `WO-CLEANUP-GAME-DATA-STATS-DEAD-KEYS`: the audit claimed
`SHIP_PRICES_COUNT_KEY` / `HOLD_PRICE_LABEL_KEY` were write-only. Tip
consumers already read the status string keys — stamp that honesty and
route readers through the named constants so the symbols stay load-bearing.

## Scope

- `tw2002_aiclient/game_data_stats.py` — consumer cite in module doc
- `tw2002_aiclient/focus_status.py` — read via constants
- `tw2002_aiclient/cockpit/goals.py` — read via constants
- `tw2002_aiclient/stardock_hold_plan.py` — read via constant
- `tests/test_game_data_stats.py` — consumer-import pin
- This WO file

## Accept

1. Grep: `goals.py` / `focus_status.py` / `stardock_hold_plan.py` import or
   reference `SHIP_PRICES_COUNT_KEY` / `HOLD_PRICE_LABEL_KEY`.
2. Existing `test_game_data_stats` + focus/goals pins stay green.
3. live-prove: `n/a` (status-key honesty; no login/session surface).

## Proof

`pytest tests/test_game_data_stats.py tests/test_focus_status.py tests/test_cockpit_goals.py -n0` · STATUS SHA.

## Refs

queue-aiclient `WO-CLEANUP-GAME-DATA-STATS-DEAD-KEYS` · hub ACK on #409
