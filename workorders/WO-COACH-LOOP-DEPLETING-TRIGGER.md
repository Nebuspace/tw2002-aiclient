# WO-COACH-LOOP-DEPLETING-TRIGGER

**Status:** DONE · origin `c49819b` (#258) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Depends:** `main` ≥ `4d26eac`

## Goal

Close coaching canon's explicit unreachable-card gap: when an armed loop halts
for depletion, surface the authored `loop_depleting` strategy card in the idle
DECISIONS pane. This teaches the operator; it never rotates, restarts, arms, or
sends.

## Canon

`canon/engine/coaching-engine.md` names `loop_depleting` as authored but
unreachable. Existing `status["intervention"]["reasons"][].code` safely exposes
typed halt codes without prompt text. Canon classifies `floor_reached` and
`turn_budget_exhausted` as depletion.

## Scope

- `tw2002_aiclient/coach_engine.py`
  - Add a strict, fail-closed `loop_depleting` input to
    `infer_coach_triggers()`.
  - Emit `loop_depleting` in stable order only for genuine `True`; hostile
    truthy values must not trigger.
- `tw2002_aiclient/cockpit/decisions.py`
  - Read only the existing intervention reason-code list.
  - Treat exactly `floor_reached` and `turn_budget_exhausted` as depletion.
  - Pass the derived boolean to the coach; malformed/unknown shapes stay
    silent.
- `tests/test_coach_engine.py`
  - Positive/negative/stable-order and reachable-card-set pins.
- `tests/test_cockpit_decisions.py`
  - Both depletion reasons render the authored route-longevity card when the
    trace is idle.
  - Near-miss/unknown/malformed intervention does not.
  - Existing autopilot trace still wins.

## Constraints

- Read-only coaching only: no sends, no arm, no restart/rotation.
- No daemon/status schema change; consume the existing redacted intervention
  block.
- Never add or request `prompt` on status.
- Card prose comes only from `data/coach/strategies.json`.
- No shared operator `run/` touch.
- Cursor Task usage is exhausted this session: implement from the lead seat;
  do not spawn subagents.

## Accept

1. `infer_coach_triggers(loop_depleting=True)` emits `loop_depleting`; false,
   absent, malformed, or merely truthy values do not.
2. Idle DECISIONS renders the authored `loop_depleting` card for
   `floor_reached` and `turn_budget_exhausted`.
3. Unknown/malformed intervention reasons remain honest-empty.
4. A non-empty `autopilot_trace` keeps priority over coaching.
5. Reachable-card pin leaves only `planet_management` unreachable.
6. Focused tests and full offline suite green.
7. live-prove: `n/a` — read-only composer wiring with offline integration pins.

## Proof

```bash
pytest -q tests/test_coach_engine.py tests/test_cockpit_decisions.py
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- `canon/engine/coaching-engine.md` I2 + Code divergence
- `canon/architecture/control-and-escalation.md`
- `session/autoloop.py::intervention_block`
- Plan: Nebuspace
  `.samantha/plans/coach-loop-depleting-trigger-2026-07-30.md`

