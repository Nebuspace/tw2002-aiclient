# WO-UNKNOWN-CLASSIFY-SEND-REFUSE-PIN

**Status:** OPEN · READY · offline · Cursor preferred (or CC)  
**Posted:** 2026-07-26 · CC 21:50:58Z after #40 (hub merged before reading — follow-on, not revert)

## Goal

`WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN` (#40) correctly re-aims password-length chrome to `unknown`. That screen now halts by **omission** (no consumer matches `unknown`), not by C-06's explicit `money_prompt` refuse pins.

Pin the premise: **no classify→send consumer acts on `unknown`** — convert safety-by-omission into safety-by-assertion (mirror C-06's `test_no_consumer_acts_on_merely_being_recognized` shape).

Also: qualify any "halt by contract" wording in audit/#40 Accept residue — honest: correct class; halt by omission until this pin lands.

## Scope

- Pins in `tests/test_never_auto_action.py` and/or `tests/test_classify.py`
- Optional one-line audit stamp in chain-loadbearing note
- **Out:** Explore HOLD · put `unknown` into `NEVER_AUTO_ACTION_CLASSES` (wrong — never-auto is for recognized-but-forbidden) · revert #40 · live

## Accept

1. Pin(s): every inventoried classify→send consumer refuses / no-ops on `unknown` (no keystroke send).
2. Pin fails if a consumer gains an `unknown` send path.
3. Audit/chain note mentions #40 moved a screen out of the pinned refuse class into omission-until-this-pin.
4. pytest green.

## Refs

CC 2026-07-26T21:50:58Z · #40 `60365fa` · C-06 `tests/test_never_auto_action.py`
