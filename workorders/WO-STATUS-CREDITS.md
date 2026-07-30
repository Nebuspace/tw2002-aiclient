# WO-STATUS-CREDITS

**Status:** READY  
**Depends:** `main` ≥ `7397396` (#261)

## Goal

Wire top-level `status["credits"]` from the existing sticky
`session.credits_snapshot()` so the GOALS Credits row stops starving.
Observation already runs on the status path (`observe_credits`); this WO
only emits the top-level key. Capture-only; no new screen dialect.

## Canon / honesty

`tests/test_status_vocabulary_guard.py` lists `credits` as T2 unwired.
`WO-HUD-STATUS-BRIDGE` already supplied `hud.credits` from the same sticky —
the guard correctly keeps top-level `credits` distinct until a producer
writes it. Flip the guard when supplied.

## Scope

- `session/protocol.py` `_status_response`: when `credits_snapshot()` is
  `OUTCOME_READ`, set `credits` to the int balance; omit otherwise (never
  invent 0 from absence).
- Do **not** re-plumb observe (already called). Do not expand HUD cells.
- Update `tests/test_status_vocabulary_guard.py` (remove starved entry).
- Pins for emit/omit + GOALS consumer using status-shaped dicts.
- No prompt field. No send/arm/rotation.

## Constraints

- Do not touch shared operator `run/` without hub DEPLOY-WINDOW (daemon must
  restart to serve new status keys). Prefer exclusive `--run-dir` for any
  live proof.
- Lead-seat direct (no Task/subagents this session).
- Smallest change: top-level status key only.

## Accept

1. After a screen that states a strict credits balance has been observed,
   `status` includes `credits` as that int.
2. Never-observed → key omitted (GOALS stays `?`).
3. Vocabulary guard no longer lists `credits` as starved.
4. Focused + full offline suite green.
5. live-prove: offline status pins preferred; if live daemon prove is used,
   exclusive run-dir + note restart; diversity bar only if touching
   login/ensure/play arm paths (this WO should not).

## Proof

```bash
pytest -q tests/test_status_vocabulary_guard.py tests/test_cockpit_goals.py
# plus any new protocol status pin module
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- `session/session.py` `observe_credits` / `credits_snapshot`
- `session/state_parser.py` `read_credits_balance`
- `cockpit/goals.py` Credits row
- Plan: Nebuspace `.samantha/plans/status-credits-2026-07-30.md`
