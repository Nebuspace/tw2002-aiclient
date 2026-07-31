# WO-STATUS-FIGHTERS-ABOARD

**Status:** DONE · origin `7397396` (#261) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Depends:** `main` ≥ `df862ad` (#260)

## Goal

Wire top-level `status["fighters_aboard"]` from the existing sticky
`session.fighters_snapshot()` so GOALS Fighters and coach `at_shipyard`
(fighters==0) stop starving. Capture-only; no new screen dialect invention
beyond what `read_fighters_aboard` already accepts.

## Canon / honesty

`tests/test_status_vocabulary_guard.py` still lists `fighters_aboard` as T3
("needs screen parsing"), but tip already has `read_fighters_aboard` +
`observe_fighters` + `fighters_snapshot` — this is a **T2 unwired extractor**,
not a greenfield parser. Flip the guard when supplied.

## Scope

- `session/protocol.py` `_status_response`: when `fighters_snapshot()` is
  `OUTCOME_READ`, set `fighters_aboard` to the int; omit otherwise (never
  invent 0 from absence).
- Ensure observe path already feeds the sticky on status/do/screen settle
  paths that already call sibling observes — add only if a proven gap exists
  (do not drive new sends).
- Update `tests/test_status_vocabulary_guard.py` (remove starved entry).
- Pins for emit/omit + GOALS/coach consumers using status-shaped dicts.
- No prompt field. No send/arm/rotation.

## Constraints

- Do not touch shared operator `run/` without hub DEPLOY-WINDOW (daemon must
  restart to serve new status keys). Prefer exclusive `--run-dir` for any
  live proof.
- Lead-seat direct (no Task/subagents this session).
- Smallest change: top-level status key only — do not expand HUD cell set
  unless already required by an existing Accept pin.

## Accept

1. After a screen that states fighters aboard has been observed, `status`
   includes `fighters_aboard` as that int.
2. Never-observed → key omitted (GOALS stays `?`; coach shipyard arm silent).
3. Vocabulary guard no longer lists `fighters_aboard` as starved.
4. Focused + full offline suite green.
5. live-prove: offline status pins preferred; if live daemon prove is used,
   exclusive run-dir + note restart; diversity bar only if touching
   login/ensure/play arm paths (this WO should not).

## Proof

```bash
pytest -q tests/test_status_vocabulary_guard.py tests/test_cockpit_goals.py tests/test_coach_engine.py
# plus any new protocol status pin module
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- `session/session.py` `observe_fighters` / `fighters_snapshot`
- `session/state_parser.py` `read_fighters_aboard`
- `cockpit/goals.py` Fighters row · `coach_engine.py` `at_shipyard`
- Plan: Nebuspace `.samantha/plans/status-fighters-aboard-2026-07-30.md`
