# WO-PWO-107-SHIP-UPGRADE-DECISION-PORT

**Status:** build (PWO-107 Option A)
**Hub GO:** 2026-08-03T13:59:00Z C-Option-A (C-Option-B declined)

## Goal
Port archive `ship_upgrade_decision` as recommend-only; wire DECISIONS/coach from `UpgradeDecision`. Zero purchase adapter.

## Scope
- `tw2002_aiclient/ship_upgrade_decision.py` (port + status/compose helpers)
- `tw2002_aiclient/cockpit/decisions.py` (prefer UpgradeDecision callouts when status carries inputs)
- `tests/test_ship_upgrade_decision.py`
- this WO

## Accept
- Pure `choose_upgrade` / five TW-30 gates green under `tw2002_aiclient` import path.
- `compose_decisions_lines` surfaces UpgradeDecision when status carries `upgrade_decision` or catalog/player/loop inputs.
- No purchase send / StarDock buy adapter in this WO.

## Proof
`pytest tests/test_ship_upgrade_decision.py` · live-prove n/a (recommend-only; no money send).

## Out of scope
C-Option-B purchase adapter behind armconfirm (needs fresh GO).
