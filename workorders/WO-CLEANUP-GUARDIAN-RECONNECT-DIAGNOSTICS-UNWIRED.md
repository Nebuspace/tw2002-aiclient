# WO-CLEANUP-GUARDIAN-RECONNECT-DIAGNOSTICS-UNWIRED

**Status:** OPEN (in PR)
**Priority:** LOW
**Claimed-by:** impl-aiclient-cursor
**Source:** cycle-49 audit 2026-08-10 · queue-aiclient.md

## Goal

Surface SessionGuardian `last_reconnect_error` / `reconnect_count` on the `status` diagnostics payload (they were recorded but never consumed), matching resilience-and-reconnect.md's shipped framing — or retire them if intentionally debug-only.

## Tip-verify (2026-08-10 @ origin/main `4a0b8d88`)

| Check | Result |
|---|---|
| Record sites | `guardian.py` init + `_maybe_reconnect` / tick catch |
| STOP consumer | `reconnect_exhausted` → `status["intervention"]` (`protocol.py`) |
| Error/count consumer | **none** (grep) |
| Canon | resilience-and-reconnect.md already says record + surface |

## Decision

**Wire, do not drop.** Sibling sticky flag is already on the STOP banner; the error string and success counter belong on `status["reconnect"]` for operators/spectators. `last_reconnect_error` is closed-vocabulary / type-name by construction (LoginError / OSError / `guardian_tick_error:Type`) — safe on the status wire.

## Accept

- [ ] When `server.guardian` is attached, `status["reconnect"]` is `{count, exhausted, last_error}`
- [ ] Exhausted intervention reason may carry `detail` = last_reconnect_error
- [ ] Focused guardian status tests green; e2e status exact-key pin updated
- [ ] Canon names the `status["reconnect"]` diagnostics block

## Proof

```bash
.venv/bin/python -m pytest tests/test_guardian.py -q -n0
.venv/bin/python -m pytest tests/test_status_prompt_redaction.py -q -n0 -k status_carries_only
```

## live-prove

`n/a` — offline session-recovery diagnostics rail; no TWGS login/arm required for Accept kernel.
