# WO-ARM-CONFIRM-EXPLICIT-EXPLORE — explore arm must not be the bare default

**Status:** DONE · origin `b25b158` (#120) · tip-honesty stamp 2026-07-31 (product on main; banner was stale OPEN)
**Posted:** 2026-07-27T21:21:00Z · hub from CC #116 mid-build hazard  
**Seat:** open (after #116 lands — same `app.py` seam)  
**Depends:** prefer `main` ≥ #116 Accept (Play autoloop start)  
**Refs:** CC 2026-07-27T21:16:00Z · `app.py` ~867 bare `if action == "arm_confirm":` → explore

## Goal

Make the explore confirm branch **explicit**: only fire `explore_start` when `pending_confirm_action == "explore"`. A bare `arm_confirm` fallthrough must not start explore (or any runner).

Today relaunch claims an earlier branch; a third arm type (taught-loop) that forgets its own branch would take `y` and start **explore** — money-path confusion between runners.

## Accept

1. Explore start path requires `pending_confirm_action == "explore"` (or equivalent explicit discriminator).
2. Pins: loop-confirm must not call `explore_start`; explore-confirm must not call `autoloop_start` (may already land in #116 — keep or extend).
3. Unknown / unset pending + `arm_confirm` → no runner start (fail closed / ignore).
4. PR + STATUS · suite green.

## Proof

Unit/FakeClient; grep that bare explore fallthrough is gone.
