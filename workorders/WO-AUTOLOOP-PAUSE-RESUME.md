# WO-AUTOLOOP-PAUSE-RESUME — Runner-side pause/resume for taught runs

**Status:** OPEN · READY  
**Posted:** 2026-07-27T15:12:00Z · hub queue refill after P5 teach wave  
**Seat:** open — prefer Claude Code (origin: WO-P5-071 scope carve-out)  
**Depends:** `main` ≥ `11595d8` (panic/stop + `adapters.autoloop_stop`)  
**Refs:** CC 071 DECISION (A) · `session/autoloop.py` · `app-autopilot-model.md` pause/stop-able

## Goal

Add real **pause** / **resume** on `AutoLoopRunner` and wire cockpit intents so Space (or reserved key) pauses a live taught run and resume continues — not `unavailable` stubs.

## Scope

- `session/autoloop.py`: thread-lifecycle `pause()` / `resume()` (or equivalent) with clear state
- Protocol/adapters: `autoloop_pause` / `autoloop_resume` (or extend status) — honest errors, never silent success
- Cockpit: intent keys + strip affordance; layout must not clobber liveness under width pressure
- Tests: FakeClient / runner unit + wire-gap pin for new keys

## Constraints

- **Safety surface** — daemon-core thread lifecycle; mack-friendly pins; no bare Enter as confirm for arm/launch
- Panic/stop path stays **not** confirm-gated (already shipped)
- Do not invent Trade-Loop-Chains popup (separate WO)
- No new external deps

## Accept

1. Pause halts further sends while keeping session; resume continues.
2. Intent keys reach adapters; wire deletion goes red.
3. PR + STATUS with suite green.

## Proof

Unit runner state machine + suite CI; live prove n/a unless hub asks.
