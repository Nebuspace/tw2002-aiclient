# WO-BUILD-ASSIGN-TRIGGER-REKEY

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** MED (Cycle-43)  
**Depends-on:** hub ruling 2026-08-06T15:49Z (orchestrator)

## Goal

Close the Assign-Trigger calm-band residual per hub ruling: **retire** the calm
binding (not remap to a new letter). Tip-stamp canon; pin that no printable calm
key emits `assign_trigger`. Keep backend + `app.py` handler for non-calm callers.

## Hub ruling (authoritative)

> no new calm-key letter needed. Implement per the WO as literally scoped —
> `T` → `trade_loop_toggle` only, `assign_trigger`'s calm-path binding simply
> removed (the backend/non-calm entry points … are unaffected).

## Scope

- `canon/surfaces/mode-line-and-teach-controls.md` — residual closed / RETIRED stamp
- `tests/test_cockpit_assign_trigger.py` — docstring + calm-band pin
- this WO file

## Out of scope

- New calm key letter
- Deleting `assign_trigger.py` / `app.py` handler
- Remapping STOP banner teach line beyond current `A)nalyze  R)ecord`

## Accept

1. Canon no longer promises a follow-on calm re-key.
2. Calm `T`/`t` → `trade_loop_toggle` (already tip); no printable calm key → `assign_trigger`.
3. Offline assign_trigger tests green.

## Proof

```bash
.venv/bin/python -m pytest tests/test_cockpit_assign_trigger.py -q -n0
```

Live-prove: **n/a** (docs + offline key-intent pins; no session/login/play path change).
