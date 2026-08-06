# WO-BUILD-DETERMINISTIC-NAV-EXECUTOR

**Status:** IN PROGRESS  
**Priority:** MED  
**Gated:** no (hub GO 2026-08-06 — strictly taught/armed-gated)

## Goal

Daemon-side keystroke execution of a `plan_nav` route. Fires only when
`is_armed()` is true; refuses `action`-kind edges (taught-rule gate). Unarmed
must never send.

## Scope

- `tw2002_aiclient/menu/nav_exec.py` — `run_nav`
- `tests/test_nav_exec.py` — antifire pin + action refusal + happy path
- `canon/engine/menu-map-and-introspection.md` — tip-stamp divergence

## Taught/armed antifire (PR statement)

`run_nav` requires `is_armed: Callable[[], bool]`. If `not is_armed()` at entry
**or** before any step, returns `halted`/`not_armed` with `sends_issued=0`.
There is no default-true arm. Callers that want execution must supply a
predicate that is true only after human teach/arm (same shape as
`stardock_hold_driver` / `trade_driver.run_chain`).

## Accept

1. Unarmed → zero sends (unit pin).
2. `action` step → refuse without send.
3. Armed `nav` path → sends keys; stop-on-unknown on off-map.
4. live-prove: n/a (offline kernel; live wire is a later consumer).

## Proof

```bash
.venv/bin/python -m pytest tests/test_nav_exec.py -q -n0
```
