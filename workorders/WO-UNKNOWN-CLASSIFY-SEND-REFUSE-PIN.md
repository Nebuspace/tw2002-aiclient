# WO-UNKNOWN-CLASSIFY-SEND-REFUSE-PIN

**Status:** OPEN · READY · offline · Cursor preferred (or CC)  
**Posted:** 2026-07-26 · CC 21:50:58Z after #40 (hub merged before reading — follow-on, not revert)

## Goal

`WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN` (#40) correctly re-aims password-length chrome to `unknown`. That screen halts because **`unknown` is canon's escalate trigger** (`engine/screen-understanding.md`, "The Unknown Is First-Class") and every consumer is a positive match on a named class or a denylist — never "act unless unknown". It does **not** halt via C-06's `money_prompt` refuse pins, and it is **not** unguarded.

**Corrected premise (CC 2026-07-26T21:56:07Z).** This WO was requested on the mistaken belief that `unknown` was safe only by omission. It is not: `tests/test_never_auto_action.py` already states and pins the consumer shape that guarantees it.

Assert the canonical property explicitly: **no classify→send consumer acts on `unknown`** (mirroring C-06's `test_no_consumer_acts_on_merely_being_recognized` shape). Worth landing not because a gap exists, but because a property stated in canon and implied by a consumer shape should fail a test when it stops being true, rather than needing reconstruction from a module docstring.

Also: #40's original "halt by contract" wording was closer to correct than the "omission" correction applied to it — the contract is canon's escalate-first rule.

## Scope

- Pins in `tests/test_never_auto_action.py` and/or `tests/test_classify.py`
- Optional one-line audit stamp in chain-loadbearing note
- **Out:** Explore HOLD · put `unknown` into `NEVER_AUTO_ACTION_CLASSES` (wrong — never-auto is for recognized-but-forbidden) · revert #40 · live

## Accept

1. Pin(s): every inventoried classify→send consumer refuses / no-ops on `unknown` (no keystroke send).
2. Pin fails if a consumer gains an `unknown` send path.
3. Audit/chain note records that #40 moved a screen from one pinned halt (`money_prompt` denylist) to another (`unknown` escalate-first) — two mechanisms, both guarded.
4. pytest green.

## Refs

CC 2026-07-26T21:50:58Z · #40 `60365fa` · C-06 `tests/test_never_auto_action.py`
