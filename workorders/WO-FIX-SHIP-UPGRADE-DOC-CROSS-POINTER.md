# WO-FIX-SHIP-UPGRADE-DOC-CROSS-POINTER

**Status:** IN FLIGHT (this PR)
**Queue:** queue-aiclient.md (audit 2026-08-09 READY residual)

## Goal

Keep Mode-line honesty about `S)hip Upgrade·ON` (still gates **no spend**) while
removing the false claim that no ship-upgrade decision engine exists.

## Verify-first (origin/main @ 5501d350)

- `ship_upgrade_decision.py` exists; `cockpit/decisions.py` imports it for
  recommend-only `UpgradeDecision` callouts.
- `canon/strategy/ship-progression.md` already forward-points at the Mode-line
  "gates nothing yet" caveat (prior tip-true half of this row).
- Stale absences remaining on tip:
  - `canon/surfaces/mode-line-and-teach-controls.md` § Policy-auto
  - `tw2002_aiclient/cockpit/teachband.py` module docstring
  - `tw2002_aiclient/screens.py` PlayShellScreen field comment

## Change

Rewrite the three sites to: decision engine = live recommend-only; Mode-line
`S` still gates nothing because purchase / `AutonomyOffer` spend is absent.

## Accept

- Zero remaining "no ship-upgrade engine or offer kind exists" strings on tip paths above.
- "gates nothing yet" retained for the spend/toggle meaning.
- No behavior change.

## Proof

- `git grep -n 'no ship-upgrade engine'` → empty on product+canon paths touched.
- Docs/comments only → live-prove n/a.
