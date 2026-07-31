# WO-FOCUS-PTY-WAIT-FRAME

**Status:** READY · EXECUTE · MED · follow-on from #300 Concerns
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/FOCUS-PTY-WAIT-FRAME`
**Depends:** `main` ≥ `13a6ecf` · gutter width 44 (`FULL=170` / `LEFT=146` / `RIGHT=126`)

## Why

`tests/test_cockpit_focus_pty.py` narrow-tier cases ERROR with `wait_frame` stall (`assert 'wait_frame' == 'done'`) at **40×142** even when a settled grid eventually paints. Post–gutter-widen, **142 raw cols is no longer the intended “narrow left still present” band** (need inner ≥146 → raw ≥148). Stale fixture size + brittle wait is suite noise.

## Goal

Focus pty narrow/wide fixtures match current fold floors; `wait_frame` completes reliably (or honest skip with reason). Suite green without ignoring these tests.

## Scope

1. Tip-check which focus_pty tests still ERROR; note sizes vs `LEFT_GUTTER_MIN_COLS` / `RIGHT_GUTTER_MIN_COLS`.
2. Bump fixture cols into the correct tier (e.g. narrow-with-goals ≥148 raw; true right-only in `[128,148)`).
3. Fix `wait_frame` / settle signal if still flaky after size fix (timeout, predicate, ensure/daemon stub).
4. Pins green `-n0`; full suite green (no ignore of these tests).
5. This WO on the branch.

## Out of scope

#283 · product FOCUS composer changes unless required for settle · CONN glyph (#300 done).

## Accept

1. Named focus_pty narrow/wide tests green without ERROR/`wait_frame` stall.
2. Fixture sizes coherent with layout constants (comment why).
3. Suite green.

## Proof

pytest focus_pty + suite; live-prove `n/a`. No self-merge.

## Refs

`tests/test_cockpit_focus_pty.py` · `cockpit/layout.py` fold floors · #300 STATUS Concerns
