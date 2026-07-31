# WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS

**Status:** READY · BANKED · HIGH · Max GO 2026-07-31 (trainer strip redesign wave 2/3)
**Seat:** `impl-aiclient-cursor` (after WO-PLAY-STRIP-TRAINER-CHROME merges)
**Branch:** `wo/LEFT-GUTTER-NEST-FOCUS-FORMATIONS` (hub seeds at HANDOFF)
**Depends:** DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`

## Why

Left gutter shipped as sibling GOALS-over-FOCUS. Max’s model: **one GOALS box with FOCUS nested inside**; the tall leftover column is **FORMATIONS** extending toward LOGS.

## Goal

Layout + draw: nested Focus-in-Goals; tall Formations panel (honest-empty OK if catalog still banked).

## Scope

1. `layout.py` / `screens.py`: GOALS outer region contains nested FOCUS chrome (box-in-box).
2. Retarget leftover left column (today’s `left_gutter` FOCUS slot) to **FORMATIONS** title + composer (new or port `compose_formations_panel`; honest-empty if no catalog).
3. Formations panel height extends toward LOGS (claim spare left-column height intentionally).
4. Update fold path so narrow fold still honest for Goals/Focus/Formations.
5. Pins: geometry (Focus inside Goals bounds; Formations below Goals, above LOGS); titles visible.
6. Canon amend `trainer-cockpit.md` ASCII to nested Goals⊃Focus + tall Formations.
7. This WO file on the branch.

## Out of scope

- Strip chrome (WO1) · App-armed auto / Mode=halt (WO3).
- Full TW-16 formations catalog if still banked — panel chrome + honesty first.
- Fake formation counts.

## Accept

1. Focus drawn nested inside Goals box (not sibling peer of equal stack).
2. Tall Formations panel occupies left column below Goals down toward LOGS.
3. Suite green · live-prove **n/a** (layout).

## Proof

```bash
.venv/bin/python -m pytest tests/test_cockpit_layout.py tests/test_cockpit_fold.py tests/test_cockpit_fold_pty.py tests/test_cockpit_goals*.py tests/test_cockpit_focus*.py -n0 --tb=line
```

## Refs

- `.samantha/plans/play-strip-autonomy-keys.md` § Left gutter
- `canon/surfaces/trainer-cockpit.md`
