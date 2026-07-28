# WO-CONTROL-STRIP-LINE-RETIRE-OR-WIRE — compose_control_strip_line disposition

**Status:** BANKED · LOW · Cursor-class OK  
**Posted:** 2026-07-28T03:45Z · hub from CC sweep (downgraded from DELETE)  
**Refs:** CC STATUS 2026-07-28T03:44:20Z · `cockpit/control_seat.py:631` · precedent #109

## Goal
`compose_control_strip_line` has **zero product callers** but **5 test files** + maintained
sibling docs with `compose_control_strip_segments`. Not mechanical delete.

## Accept
Hub-ruled disposition in STATUS: (a) wire to product, or (b) retire helper+tests together with
honesty, or (c) keep as shared-helper surface with a product caller stub documented.
Suite + STATUS.

## Constraints
Do not delete tests without a ruling. Public-repo safe.
