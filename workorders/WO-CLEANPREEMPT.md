# WO-CLEANPREEMPT — take_human clean-preempt + attach secret redaction

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** · tip **`f3da5c6`** (CC; Lane B of P2-056 wave)
> Type: harden · Phase: 4 · Seat: impl-claudecode-aiclient
> Refs: `control_lock.py` · `attach_client.py` · `send_raw` log

## Goal
Lane B of the P4-056 HANDOFF wave:
1. `take_human` clean pre-empt: fence in-flight AI actions cleanly before Human mode takes over (no wire-interleave between AI and Human sends).
2. Attach secret redaction: close 3 secret sinks — `send_raw` log, `last_sent`, status-verb round-trip sweep (whole-JSON).

Note: Redaction proof `test_tx_record_honesty`-style coverage was already partially present at `582c210`; this WO confirmed the pre-existing coverage and closed the status-verb gap only. Lane did NOT duplicate existing tests.

## Scope
- `control_lock.py` — clean pre-empt logic
- `attach_client.py` — `send_raw` / secret redaction
- `send_raw` — log path

## Accept
- `take_human` cleanly pre-empts in-flight AI actions
- `send_raw` log never contains raw secrets
- `last_sent` never contains raw secrets
- Status-verb round-trip whole-JSON sweep passes

## Refs
CC STATUS @ impl-claudecode-aiclient:1350 · SHA `f3da5c6` · committed "WO-CLEANPREEMPT — take_human clean-preempt + attach secret redaction (fence in-flight AI, no wire-interleave, close 3 secret sinks)" · prior redaction baseline `582c210` + `190bd09`
