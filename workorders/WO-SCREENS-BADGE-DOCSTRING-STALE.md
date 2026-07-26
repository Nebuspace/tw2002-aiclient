# WO-SCREENS-BADGE-DOCSTRING-STALE

**Status:** OPEN · READY · docs honesty · Cursor · banked hub discovery 2026-07-26
**Posted:** 2026-07-26 · from `canon/findings.md` P5-064-SCREENS-BADGE-DOCSTRING

## Goal

`screens.py` module docstring still claims there is no dynamic App/Human mode badge — stale vs
060 LIVE `control_seat` chip. Align the docstring to shipped reality (or delete the false claim).

## Scope

- `tw2002_aiclient/screens.py` module docstring only (plus a one-line findings stamp if needed)
- **Out:** UI redesign; chip behavior changes

## Accept

- Docstring matches shipped control-seat / App|Human badge behavior at tip
- No product logic change required unless docstring discovery finds a real lie in code (then STOP and escalate)

## Proof

`git show` docstring + tip SHA.
