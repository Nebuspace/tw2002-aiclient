# WO-AUTOLOOP-RELAUNCH-COCKPIT — Pause/relaunch cockpit intents + honest confirm label

**Status:** OPEN · READY  
**Posted:** 2026-07-27T18:01:00Z · follow-on to #101 (wire already carries disclosure)  
**Seat:** `impl-aiclient-cursor` (rendering / intents; no protocol change)  
**Depends:** `main` ≥ `d891d35` (`autoloop_pause` / `autoloop_relaunch` + disclosure fields)  
**Refs:** #101 STATUS · hub ruling (1)+(3) · `cockpit/panic.py` (pause was descoped; now unblocked) · `cockpit/armconfirm.py`

## Goal

Wire cockpit **pause** and **relaunch** intents to the adapters already on main, with a confirm gate whose **label states the money-path truth** — not a polite synonym for "resume."

## Scope

- Cockpit intents / key bindings for pause (stand-down that keeps relaunch eligibility) and relaunch
- Confirm gate for **relaunch only** (pause may be ungated like panic — halt direction; relaunch spends)
- Confirm **label must render meaning**, using wire fields already returned by `adapters.autoloop_relaunch`:
  - `replays_from_start` (always true today)
  - `sends_already_issued` (`int` or `None` — unknown is not zero; show `?` when `None`)
  - Example shape: `replays from the beginning — N sends already issued` (or `?` for unknown)
- Update `cockpit/panic.py` stale "Pause/resume is deliberately absent" block to point at pause/relaunch reality (honest docs, no behavior change to panic)
- Tests: intent → adapter verb; confirm label pins meaning (not just field presence); wire-gap / deletion goes red for new keys
- Optional strip affordance if it fits width-pressure rules without clobbering liveness

## Constraints

- **No protocol / adapter verb changes** — wire already ships disclosure; this WO is rendering + binding only
- **Never** name the key/verb/UX "resume" — that word stays refused (`autoloop_resume` = `unknown_verb`)
- Relaunch is confirm-gated (money path); bare Enter must not fire relaunch
- Panic stays **not** confirm-gated
- No new external deps; stay in cockpit / screens / tests lanes

## Accept

1. From a paused taught run, cockpit can pause (if not already) and relaunch via intents that call `adapters.autoloop_pause` / `adapters.autoloop_relaunch`.
2. Relaunch confirm label discloses **replay-from-start** and **sends already issued** (or `?`); a label that only echoes raw JSON field names without meaning fails Accept.
3. `autoloop_resume` / "resume" UX strings do not appear in cockpit affordances.
4. Suite green; PR + STATUS.

## Proof

Unit/PTY cockpit tests + suite CI; live-prove n/a (no new daemon money path — disclosure already unit-pinned on #101).
