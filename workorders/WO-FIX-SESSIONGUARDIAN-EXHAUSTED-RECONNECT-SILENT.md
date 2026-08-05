# WO-FIX-SESSIONGUARDIAN-EXHAUSTED-RECONNECT-SILENT

**Goal:** Stop SessionGuardian from silently forever-retrying after reconnect+replay exhausts; surface a typed STOP reason instead.

**Scope:**
- `tw2002_aiclient/session/guardian.py` — sticky `reconnect_exhausted`
- `tw2002_aiclient/session/protocol.py` — `status["intervention"]` wire
- `tw2002_aiclient/cockpit/stopbanner.py` + canon catalog — label `reconnect_exhausted`
- tests for sticky suppress / clear / status wire / no auto-MODE_HUMAN

**Depends-on:** none (hub GO 2026-08-05T15:11:09Z)

**Accept:**
1. After N failed reconnect attempts, further poll ticks do **not** re-enter the attempt loop while sticky.
2. `status` includes `intervention` with code `reconnect_exhausted` while sticky.
3. Sticky clears on successful D9 reconnect, `clear_reconnect_exhausted()`, or observing connected again.
4. No auto-`MODE_HUMAN` as a side effect of exhaustion.

**Proof:** focused pytest on `tests/test_guardian.py` + `tests/test_cockpit_stopbanner.py` catalog pin; live-prove n/a (offline session-recovery rail — no TWGS login/arm required for Accept kernel).

**Refs:** `canon/architecture/resilience-and-reconnect.md` · `canon/surfaces/trainer-cockpit.md` (`reconnect_exhausted`) · hub GO A+B+C
