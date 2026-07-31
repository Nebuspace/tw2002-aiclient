# WO-STRIP-HOTFIX-FIT-TRADE-LOGS

**Status:** READY · EXECUTE · HIGH · Max GO 2026-07-31 ("dont wait… go fix")
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/STRIP-HOTFIX-FIT-TRADE-LOGS`
**Depends:** `main` ≥ `e6ef566` (#298)

## Why

1. **Teachband invisible** under ~128–140 strip cols: calm band is ~105 chars; `_compose_segments` all-or-nothing-drops it. Pins used 40×180 — Ada rage-quit on normal laptop widths.
2. **False "starting trade"**: `_autonomy_auto_fire` sets LOGS `App-armed — starting trade…` *before* `trade_chain_start`; on `ok=False` leaves that line and returns quiet — operator thinks trading is happening.

## Goal

Keybinds visible at common widths; App-armed trade refuse is honest in LOGS.

## Scope

### A — Teachband progressive fit (Max option 1)

1. Under width pressure, **do not** drop the whole band first. Progressive shrink, prefer keeping `E` / `P` / `T` / `L` visible.
2. Suggested ladder (implementer may refine with pins): full labels → shorter toggle forms (`P)ort·ON`, `C)argo·ON`, `S)hip·ON`) → drop `│` padding / `BAND_PAD` → drop ship/cargo tokens before E/P/T/L → only then all-or-nothing.
3. `compose_teach_band` (or a fit helper fed `budget`) must accept available width from `control_seat` (or control_seat tries ladder). Pins at strip widths **100, 120, 140** with seat+liveness(+optional COV) still showing ≥ `E)xplore` and `L)ist`/`L)oops` (or documented short forms).
4. Full calm labels remain the wide-terminal default (do not delete Max's long-label ruling — only shrink under pressure).

### B — Trade/hold start honesty

1. On `trade_chain_start` / `stardock_hold_start` `ok=False`, rewrite `status_line` with refuse reason (machine `reason` + short human), never leave stuck `starting…`.
2. Quiet-only for true no-ops if already documented (`already_running` may stay quiet *or* one-line once — prefer one honest line over stuck starting).
3. Pins: ok=False leaves LOGS/status containing refuse, not `starting trade` / `starting hold buy` as the final line.

### C

This WO file on the branch.

## Out of scope

#283 diversity · second teachband row · shortening the *default* wide-terminal labels · ship-upgrade engine.

## Accept

1. At strip width 120 with `^A)…` + typical liveness, calm keybinds still visible (not blank mid-strip).
2. Wide terminal still shows full `P)ort Trade·ON` / `C)argo Hold Upgrade·ON` / etc.
3. Auto-fire trade/hold start failure never ends on bare `starting…` without a refuse reason.
4. Focused pins green; full suite green; live-prove `n/a` OK if chrome+status_line only (state reason).

## Proof

Focused teachband/control_seat + policy_auto pins; suite; STATUS tip SHA. Do not self-merge.

## Refs

- `cockpit/control_seat.py` `_compose_segments` teachband all-or-nothing (~688–703)
- `cockpit/teachband.py` `compose_teach_band` / `BAND_PAD`
- `app.py` `_autonomy_auto_fire` ~944–964, ~974–993
- Hub diagnose 2026-07-31T22:04Z / 22:07Z
