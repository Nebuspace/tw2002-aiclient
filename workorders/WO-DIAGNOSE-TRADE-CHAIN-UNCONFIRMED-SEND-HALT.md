# WO-DIAGNOSE-TRADE-CHAIN-UNCONFIRMED-SEND-HALT

**Parent:** `WO-LIVE-WITNESS-FIRST-TRADE-LOOP` (orchestrator live-witness run, 2026-08-07,
`academy_of_tradewars` / sacrificial). This is the residual left after the run's own credit-gain
proof succeeded — not a re-open of anything already fixed.

## What the live witness found

With hop-cap (#511) and start-anchor reachability (#512) both fixed and merged, `tw chain start`
armed cleanly and **the chain earned real money**: credits 99,000 → 102,957 (+3,957) over 6/16
planned hops, 99 sends, before halting.

The halt itself is not a crash or an unhandled error — it's the designed fail-closed path.
`trade_driver.py:382`'s `_confirmed_send` raises `ChainHold(f"unconfirmed_send:{text!r}")`
whenever `settle.send_and_confirm` reports `confirmed=False` for a step, and the run stopped
cleanly at sector 10396 with reason `unconfirmed_send:'10396'`. Per `autoloop.py`'s own docstring
on the underlying mechanism (`send_and_confirm`, lines 686-688): *"a recorded `wait_prompt` that
only ever matched a BODY line can no longer be confirmed, so that step times out and the run
halts `confirm_failed`. A missed confirm, never a wrong one."* This is deliberately conservative
by design (A-M1/A-C1 fail-closed gates, per the module's own PALADIN-adjacent invariants) — the
question is *why* this particular send at sector 10396 didn't confirm, not whether the halt
itself was correct.

## Goal

Determine why the send to sector `10396` mid-chain failed to confirm, and fix the root cause so
a taught/armed trade chain can complete its full planned hop count on a normal run, rather than
diagnosing this as "expected, just re-run and hope."

## Scope

- Investigate first, using the run's own trace/history ring (`WO-ARM-HISTORY-RING`,
  `autoloop.py:_record`) and/or `tw trail` / `tw log` for the halted run — this WO's first job is
  reading what screen was actually on-wire at that step, not guessing.
- Likely candidates to check (do not assume any of these without evidence from the actual trace):
  - An unexpected screen at sector 10396 (encounter, mine, NPC, different port class than
    expected) that the recorded `wait_prompt` regex genuinely never matches — a real screen-
    pattern gap.
  - A timing/timeout issue (`step_timeout_s` too tight for that specific screen's actual settle
    time) — a tuning fix, not a pattern fix.
  - A stale/wrong `wait_prompt` baked into the taught chain step itself from when it was recorded
    — a chain-data fix, not an engine fix.
- Fix lands in whichever of `trade_driver.py`, `session/settle.py`, `session/autoloop.py`, or the
  chain step data is actually implicated — don't touch files outside what the trace points to.

## Out of scope

- Re-litigating the fail-closed design itself (A-M1/A-C1) — halting on a genuinely unconfirmed
  send is correct behavior; this WO is about why THIS send didn't confirm, not about making sends
  confirm more permissively.
- A full second live re-run to re-prove "does the loop earn" — that's already proven
  (`WO-LIVE-WITNESS-FIRST-TRADE-LOOP`, +3,957 credits). This WO's own proof is completing more
  hops on a fresh run, not re-establishing the baseline finding.

## Constraints

- Ungated, buildable now — standing carte-blanche already covers disposable/SOLO sacrificial arms
  for any live re-verification this needs.
- If the root cause turns out to be a missing screen pattern, check
  `canon/research/tw2002-screen-patterns.md` / `canon/research/archive-port-patterns.md` first —
  the pattern may already be documented and just not wired into this code path, same shape as the
  StarDock gap `WO-FIX-EXPLORE-SKIP-SPECIAL-PORTS` (#510) turned out to be.

## Accept

1. Root cause of the sector-10396 `unconfirmed_send` halt identified and stated with evidence
   (trace/log excerpt), not guessed.
2. Fix applied matching that root cause (pattern / timing / chain-data, whichever the evidence
   points to).
3. A fresh sacrificial live run on a comparable world completes more hops than the original run
   without hitting the same halt reason at the same or an equivalent step (full 16/16 completion
   is the ideal outcome but not a hard bar if a *different*, newly-surfaced halt reason is found
   and separately triaged — report whichever occurs, don't silently claim full completion if it
   wasn't observed).

## Proof

Offline: unit test pinning the specific fix (pattern regex, timeout value, or chain-data
correction) against the failure shape found. Live: sacrificial re-run per Accept #3, same
before/after credits + hop-count reporting shape as the parent WO's STATUS.

## Owner

tw2002-aiclient — `tw2002_aiclient/trade_driver.py`, `tw2002_aiclient/session/settle.py`,
`tw2002_aiclient/session/autoloop.py`, and/or the taught chain step data implicated by the trace.

## Refs

Live session: `academy_of_tradewars` (sacrificial), 2026-08-07. Credits 99000 → 102957
(+3957), halted `unconfirmed_send:'10396'` after 6/16 hops, 99 sends. Parent:
`WO-LIVE-WITNESS-FIRST-TRADE-LOOP`. `trade_driver.py:382`, `session/autoloop.py:670-699`,
`session/settle.py`.

## Evidence (2026-08-07 seat diagnose)

Session log `logs/session-20260807T063427Z.log` (sacrificial credit proof):
final TX `10396` at 06:40:46 painted Sector + Command on wire; chain did not
continue (next TX was `i` at 06:40:49). `_navigate` was confirming warps with
`confirm_prompt=None` and default `retry_unstable_idle=False`. Fix: pass
`retry_unstable_idle=True` on nav warps (same as `sector_explore` /
settle `warp_unstable`). Offline pin: `tests/test_trade_nav_retry_unstable_idle.py`.
