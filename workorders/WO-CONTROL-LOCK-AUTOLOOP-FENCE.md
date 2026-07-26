# WO-CONTROL-LOCK-AUTOLOOP-FENCE

**Status:** OPEN · HIGH · READY · Max ruled **3A** 2026-07-26 · CC preferred (safety)
**Posted:** 2026-07-26T07:24Z
**Max ruling (3A):** **Fence** — `take_human` must stop/hold autoloop (not docs-only).

## Goal

Close the `ControlLock` gap X4 discovered: `take_human()` only raises `_driver_fenced` when `_driving` is set. A background autoloop holds `enter_auto_loop`, not `_driving` — so `is_driver_fenced()` stays False while a human is typing. X4's player works around by asking "is my hold still mine?"; the lock itself should not lie. **Product fence required.**

## Scope

- `session/control_lock.py` (+ pins) — fence / preempt semantics for auto_loop holds
- Do not weaken human-always-wins `take_human`
- Coordinate with X4 player predicate (may simplify once lock is honest)

## Constraints

- Safety-listed adjacent (control / attach) — cipher+mack on Accept if behavior changes
- Pin: naive `is_driver_fenced()` forward must not be the only story; lock truth preferred
- No fabricated ARM / mode strings

## Accept

Lock honestly signals preempt of an auto_loop hold (or documents a deliberate narrower `is_driver_fenced` + new predicate); suite proves attach mid-autoloop; X4 workaround reassessed.

## Proof

STATUS + SHA · targeted pytest (incl. X4's "fence still False at halt" may flip — update honestly).

## Refs

CC X4 STATUS 2026-07-26T06:44:06Z · `control_lock.py:102-103` · sovereign-pilot invariant
