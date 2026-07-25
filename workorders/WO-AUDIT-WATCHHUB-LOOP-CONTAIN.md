# WO-AUDIT-WATCHHUB-LOOP-CONTAIN — Contain WatchHub._loop exceptions

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`00cb9e8`** (CC · Fable 5) · docs stamp Cursor  
> Type: harden · Priority: P1 · Lens: L3 / cleanup  
> Refs: `session/watch.py` · guardian idiom `guardian.py:109-116` · polish analyze #6

## Tip verdict
**DONE** on origin `00cb9e8` — `WatchHub._loop` uses guardian-style containment; `last_loop_error` records **type-name only** (no exception text); per-subscriber put containment; stop via `_stop.wait`. Proof: `tests/test_watch.py` (hostile raise / sentinel / thread-alive). Disclosed follow-on banked: status-verb wire for `last_loop_error` in `protocol.py` — not invented in this WO.

## Goal
Wrap `WatchHub._loop()` so an uncaught raise in `_maybe_emit`/`_broadcast` cannot silently kill the watch thread forever (subscribers go dark with zero error).

## Scope (disjoint)
- A: `tw2002_aiclient/session/watch.py` — contain poll loop like guardian; log/record error; keep thread alive or restart policy documented
- B: `tests/` — hostile-input / raise-in-broadcast regression; request-time path remains contained
- C: docs — findings/bank note CLOSED when Accept’d

## Constraints
No seat-key / attach / Human→App / F2. Tripwire untouched. Prefer guardian idiom over new deps.

## Accept
1. Injected raise in broadcast path does not permanently kill hub for new subscribers
2. Error is observable (log/status), not silent
3. Suite fingerprint-bound green

## Proof
Unit FakeHub · full suite · STATUS SHA `00cb9e8` on origin. Push waits Accept (product already SHIPped).

## Refs
CC POLISH-SAFE STATUS @ 05:27:02Z · hub Accept @ 05:41:33Z · Zone-A ACK
