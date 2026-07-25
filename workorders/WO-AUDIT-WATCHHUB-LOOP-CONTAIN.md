# WO-AUDIT-WATCHHUB-LOOP-CONTAIN — Contain WatchHub._loop exceptions

> Status: **DRAFT** 2026-07-25 · from CC POLISH Zone-A BANK-P1 · tip `88004d8`  
> Type: harden · Priority: P1 · Lens: L3 / cleanup  
> Refs: `session/watch.py:90-97` · guardian idiom `guardian.py:109-116` · polish analyze #6

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
Unit FakeHub · full suite · STATUS SHA. Push waits Accept.

## Refs
CC POLISH-SAFE STATUS @ 05:27:02Z · hub Zone-A ACK
