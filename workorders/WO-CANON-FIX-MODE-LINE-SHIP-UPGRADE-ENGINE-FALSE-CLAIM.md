# WO-CANON-FIX-MODE-LINE-SHIP-UPGRADE-ENGINE-FALSE-CLAIM

**Status:** IN FLIGHT · Cursor · `wo/CANON-FIX-MODE-LINE-SHIP-UPGRADE-ENGINE-FALSE-CLAIM`
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ `59836f9` (#663 MERGED); prior honesty slice `#654` / `WO-FIX-SHIP-UPGRADE-DOC-CROSS-POINTER`
**Refs:** cycle-49 audit · hub correction 2026-08-10T04:57:43Z ·
`canon/surfaces/mode-line-and-teach-controls.md` · `tw2002_aiclient/ship_upgrade_decision.py` ·
`tw2002_aiclient/app.py` `_autonomy_auto_fire`

## Why

Cycle-49 queued this as tip-false against `mode-line-and-teach-controls.md:94`
("No ship-upgrade engine… exists") while `ship_upgrade_decision.py` is live.
Hub re-asserted NOT tip-true after #663. Verify-first on `origin/main` shows
Mode-line / teachband / `screens.py` / the policy-auto test docstring were
already corrected by **#654** (`429ce52`). Residual: `app.py` `_autonomy_auto_fire`
still says no "ship-upgrade engine" exists (conflates missing `AutonomyOffer` /
adapter spend with the recommend-only decision engine).

## Goal

Docs/comments tip-true only: recommend-only engine exists
(`ship_upgrade_decision.py`); no EXECUTE / offer-kind auto-fire is wired to
the Mode-line `S` toggle yet.

## Scope

1. `tw2002_aiclient/app.py` — `_autonomy_auto_fire` docstring residual.
2. Pin test that the stale "no ship-upgrade engine" absence claim cannot
   regress on the known surfaces (Mode-line + auto-fire docstring).
3. This WO file.

## Out of scope

- Wiring `AutonomyOffer` / `ship_upgrade_start` / Mode-line `S` spend gate.
- `WO-CANON-FIX-EXPLORATION-POLICY-STALE-4-INTENT-CYCLE` (hub HOLD / re-scope).

## Accept

1. No product/canon tip path claims a ship-upgrade *decision engine* is absent.
2. Wording keeps: `S` gates nothing for EXECUTE / offer-kind auto-fire.
3. Sibling tests do not assert the old absence prose (#653 lesson).

## Proof

- `git grep -n 'no ship-upgrade engine\|No ship-upgrade engine' -- ':!archive/**' ':!workorders/**'` empty on product+canon.
- `pytest tests/test_ship_upgrade_engine_claim_honesty.py tests/test_play_strip_policy_auto.py::test_ship_upgrade_toggle_never_reaches_any_adapter`
- `live-prove: n/a` (docs/comments only).
