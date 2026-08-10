# WO-CLEANUP-ASSIGN-TRIGGER-DOCSTRING-T-STALE

**Status:** OPEN (residual of DONE #650 / WO-BUILD-ASSIGN-TRIGGER-REKEY)

## Goal

Make Assign-Trigger tip docs/comments match calm-band reality: Play `T` is
Trade Loop Chain, not Assign-Trigger.

## Why

After #650, STOP teach chrome and mode-line canon are honest (`A)nalyze
R)ecord` only; calm `T` → Trade Loop). `cockpit/assign_trigger.py`'s module
docstring and two `app.py` comments still claimed calm `T` binds
Assign-Trigger — contradicting `screens.py` (`trade_loop_toggle`) and
`tests/test_cockpit_assign_trigger.py` (no printable calm key emits
`assign_trigger`).

## Scope

- `tw2002_aiclient/cockpit/assign_trigger.py` — module docstring
- `tw2002_aiclient/app.py` — two WO-P5-068 comments
- `workorders/WO-CLEANUP-ASSIGN-TRIGGER-DOCSTRING-T-STALE.md` — this file

## Constraints

- No new calm key / no remapping Assign-Trigger onto the calm band
- Behavior unchanged (handler + scaffold intact for non-calm callers)

## Accept

1. `assign_trigger.py` does not claim calm Play `T` binds Assign-Trigger
2. `app.py` comments do not say "T Assign-Trigger"
3. Focused assign-trigger / teachband tests stay green

## Proof

`pytest tests/test_cockpit_assign_trigger.py tests/test_cockpit_teachband.py -q -n0`
