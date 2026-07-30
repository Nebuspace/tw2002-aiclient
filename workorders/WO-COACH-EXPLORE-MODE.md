# WO-COACH-EXPLORE-MODE

**Status:** READY  
**Depends:** `main` ≥ `fb4cdf8` (#262)

## Goal

Unstarve coach card `exploring_frontier` by wiring top-level
`status["explore_mode"]` from the existing explore runner snapshot, and
passing it through `cockpit/decisions.py` into `infer_coach_triggers`.

## Canon / honesty

`infer_coach_triggers(explore_mode=…)` already maps a non-`"off"` mode to
`exploring_frontier`. Decisions currently omits the kwarg. Explore truth
already lives on `explore_status` via `explore_run_wire` — reuse that; do
not invent a second progress model. Omit the key when explore is idle
(never invent a fake mode).

## Scope

- `session/protocol.py` `_status_response`: when explore is running with a
  report, emit `explore_mode` as the report's `intent` string; when idle /
  unavailable, omit the key.
- `cockpit/decisions.py`: pass `explore_mode=_safe_str(status.get("explore_mode"))`
  (or equivalent fail-closed) into `infer_coach_triggers`.
- Pins: running → card fires; idle omit → no card; hostile/"off" → no card.
- Reachable-card pin: only `planet_management` remains unreachable (unless
  already changed — keep honest).
- No prompt field. No send/arm. No CLI default flips.

## Constraints

- Do not touch shared operator `run/` without hub DEPLOY-WINDOW. Prefer
  exclusive `--run-dir` / offline pins.
- Lead-seat direct (no Task/subagents this session).
- Smallest change: status key + decisions wire + pins.

## Accept

1. Mid-run explore → `status` includes `explore_mode` equal to the run intent.
2. Idle / no runner → key omitted; coach exploring card silent.
3. Decisions surfaces `exploring_frontier` when mode is present and not `"off"`.
4. Focused + full offline suite green.
5. live-prove: offline pins preferred (`n/a` diversity); no login/ensure/play arm.

## Proof

```bash
pytest -q tests/test_coach_engine.py tests/test_cockpit_decisions.py
# plus any new protocol status pin
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- `coach_engine.infer_coach_triggers` · `data/coach/strategies.json` exploring_frontier
- `sector_explore.explore_run_wire` / `observe_explore`
- Plan: Nebuspace `.samantha/plans/coach-explore-mode-2026-07-30.md`
