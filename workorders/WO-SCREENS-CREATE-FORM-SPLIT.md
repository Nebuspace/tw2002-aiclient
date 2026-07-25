# WO-SCREENS-CREATE-FORM-SPLIT

**Status:** OPEN · Cursor preferred (product TUI)  
**Posted:** 2026-07-25 IDLE-KICK refill (CC quality gate)

## Goal

Split `screens.py` create-form cluster out before it grows further past the 1500-line Python cap (`screens.py` ~2012 lines).

## Scope

Extract `_FORM_FIELDS` · `validate_create_form` · `_create_error_text` · `CreateFormScreen` (and minimal helpers) into a focused module; keep imports/behavior identical.

## Constraints

Behavior-neutral refactor · tests green · do before M6 create-UX lands on this file · off CC parked classify tip.

## Accept

`screens.py` line count materially reduced; create-form module owns the cluster; suite collect + create-form related tests green.

## Proof

STATUS + `wc -l` before/after + targeted pytest.

## Refs

CC disclosure — screens.py over 1500 cap; clean seam identified.
