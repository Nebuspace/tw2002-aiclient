# WO-CLEANUP-TEACHBAND-TEACH-TOKENS-WIRE-OR-RETIRE

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** LOW (Cycle-48 unused-code tick)  
**Depends-on:** none

## Goal

Wire `TEACH_TOKENS` into a real product consumer — the all-ON default path of
`compose_teach_band` — so the tuple is the SSOT for the standing calm band
(not unused scaffolding). Do not retire.

## Scope

- `tw2002_aiclient/cockpit/teachband.py` — default all-ON uses `TEACH_TOKENS`
- `tests/test_cockpit_teachband.py` — SSOT pin
- this WO file

## Accept

1. `compose_teach_band()` with default toggles joins `TEACH_TOKENS`.
2. Non-default toggle kwargs still recompute tokens dynamically.
3. Existing teachband tests green (canon spelling pin unchanged).

## Proof

```bash
.venv/bin/python -m pytest tests/test_cockpit_teachband.py -q -n0
```

Live-prove: **n/a** (offline calm-band composition; no session/login/play path).
