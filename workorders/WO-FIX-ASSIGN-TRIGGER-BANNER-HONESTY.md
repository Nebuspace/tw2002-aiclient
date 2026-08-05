# WO-FIX-ASSIGN-TRIGGER-BANNER-HONESTY

**Status:** DONE (pending merge)
**Priority:** LOW
**Gated:** no

## Goal

STOP banner advertised `T)assign` while calm `T` is Trade Loop and no key
emits `assign_trigger`. Drop the false affordance from `TEACH_LINE`; keep
Assign-Trigger module for a future re-key WO.

## Scope

- `tw2002_aiclient/cockpit/stopbanner.py`
- `tw2002_aiclient/cockpit/teachband.py` (docstring)
- `tests/test_cockpit_stopbanner.py`
- `tests/test_cockpit_stopbanner_wiring.py`
- `tests/test_cockpit_teachband.py`
- `canon/surfaces/mode-line-and-teach-controls.md`
- This WO file

## Accept

1. `stopbanner.TEACH_LINE` is `teach:  A)nalyze  R)ecord` (no `T)assign`).
2. Related pins green; teachband still claims Trade Loop on calm `T`.
3. live-prove: `n/a` (chrome honesty; no login/session surface).

## Proof

`pytest tests/test_cockpit_stopbanner.py tests/test_cockpit_stopbanner_wiring.py tests/test_cockpit_teachband.py -n0`

## Refs

#414 tip-stamp residual · WO-EXPLORE-TRADE-MODE-SPLIT
