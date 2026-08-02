# WO-CONTROL-STRIP-LINE-RETIRE-OR-WIRE — compose_control_strip_line disposition

**Status:** DONE · origin `77a687b` (#143) · tip-honesty stamp 2026-08-02 (product on main; banner was stale SEAT-DONE awaiting Accept)
**Posted:** 2026-07-28T03:45Z bank · EXEC seeded 2026-07-28T03:58Z · seat STATUS 2026-07-28T04:02Z  
**Refs:** CC sweep · screens.py already on `compose_control_strip_segments` · wire-class W7

## Goal
Dispose `compose_control_strip_line` (zero product callers; 5 test files). Product draw path
already uses **segments** (`screens.py`).

## Hub ruling (do not re-ask)
**(b) RETIRE** — remove the unused flat-string helper (and any *only*-line test surface that
cannot migrate). Prefer migrating useful pins onto `compose_control_strip_segments` parity
tests before delete. Update docstrings in `control_seat.py` / `screens.py` that still present
`compose_control_strip_line` as the live composer.

Not (a) wire — would reintroduce a dead API next to the live one.  
Not (c) keep-as-stub — no product needs the flat join.

## Accept
1. Zero remaining product **or** test imports of `compose_control_strip_line` (or tests that
   still import it must be deleted/rewritten to segments).
2. `compose_control_strip_segments` remains the sole product strip composer; suite green on
   affected cockpit/spectate/control tests.
3. STATUS cites files removed/rewritten; live-prove **n/a** (chrome helper, no login path).

## Constraints
Owned paths: `tw2002_aiclient/cockpit/control_seat.py` · `screens.py` docstring-only if needed ·
`tests/test_cockpit_*.py` that reference the line helper.  
Do **not** touch `explore.py` / formations / chains (CC #142). Public-repo safe. Explicit paths only.
