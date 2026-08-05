# WO-WIRE-PLAN-NAV-DETERMINISTIC-NAV

**Status:** DONE (pending merge)
**Priority:** MED
**Gated:** no

## Goal

Give `plan_nav` a real product consumer without wiring live keystroke
execution: dry `tw menumap --to <sig>` (never sends). Keep the send half
honestly parked in canon.

## Scope

- `tw2002_aiclient/session/cli.py` — `--to` / plan_nav call site
- `tw2002_aiclient/menu/nav.py` — PARKED note refresh
- `canon/engine/menu-map-and-introspection.md` — Code Divergence honesty
- `tests/test_cli_menumap.py`
- This WO file

## Accept

1. `tw menumap --to SIG` with a live localize prints/returns a plan and
   never calls a send verb.
2. Without a live look, `--to` exits non-zero with an honest refuse.
3. Canon states dry CLI consumer vs unbuilt daemon send half.
4. live-prove: `n/a` (offline CLI; no login/session arm).

## Proof

`pytest tests/test_cli_menumap.py -n0` · STATUS SHA.

## Refs

queue-aiclient · WO-FA14 parked planner · `menu/nav.py::plan_nav`
