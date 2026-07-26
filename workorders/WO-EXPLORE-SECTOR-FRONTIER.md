# WO-EXPLORE-SECTOR-FRONTIER

**Status:** **IN PROGRESS** · Cursor · M4 (automatic sector exploration)  
**Posted:** 2026-07-26 · Max milestone M4 (automatic sector exploration)  
**Seat:** Cursor · M4 (`wo/EXPLORE-SECTOR-FRONTIER`)  
**Depends:** ensure → `main_command` on target host · `WO-CONTROL-LOCK-AUTOLOOP-FENCE` Accepted · G4 LoopPlayer / state-sector substrate (DONE)

## Goal

From a verified `main_command`, the App automatically explores sectors (frontier / map-fill style) with **halt-on-unknown** and an honest `explore_exhausted` (or equivalent) when the budget/frontier ends — no invented screen classes, no money/combat auto-action.

## Constraints

- **Taught / safe hops only** — reuse archive AP-08 / BANKED `test_explore.py` intent; do not revive EV-every-tick guess driver.
- Stop-on-unknown · never-auto-action screens unchanged.
- Human attach always wins (fence must be Accept'd first).
- Isolated sacrificial profile; no Max live xeno drive without GO.
- No invent `screen_class` without Max GO.

## Accept

1. From `main_command` on one sacrificial host: App explores ≥N distinct sectors (N named in STATUS, default 5) without human keystrokes.
2. Unknown / unsafe screen → halt (not blind warp).
3. Exhausted frontier → labeled halt (`explore_exhausted` or documented successor), not a hang.
4. Pins cover planner unit + at least one FakeSession/FakeTWGS path; live proof on isolated run-dir after HOLD lift.

## Proof

```text
pytest tests/test_explore.py -q -n0   # rehab/unbank as needed
# live isolated: ensure → main_command → explore ≥N sectors → halt clean
```

## Refs

- `canon/architecture/control-and-escalation.md` (`explore_exhausted`)
- `canon/testing/cases/test-explore.md` (BANKED)
- `workorders/BRIEF-OKF-ARCHIVE-PORT-PATTERNS.md` (AP-08)
- Sprint plan: `.samantha/plans/ensure-game-explore-sprint-20260726.md`
