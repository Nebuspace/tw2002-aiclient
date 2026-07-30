# WO-RETIRE-CYCLE-EXPLORE-MODE — delete unwired trainer mode cycler

**Status:** DONE · origin `9763fb0` (#247) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T08:09Z · hub (post-#246; unused-code tick)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `707efa6`  
**Refs:** `explore.cycle_explore_mode` · comment at `ARMABLE_INTENTS` (formations trainer cycle stays unwired) · `#245` Play uses `next_armable_intent`

## Goal

`cycle_explore_mode` is **test-only** — Play's `E` offer uses `next_armable_intent`
(`map_fill` ↔ `find_stardock`). The fuller trainer cycle (off → mapfill →
stardock → formations) was never product-wired and `plan_find_formations` still
has no product caller. Retire the dead cycler rather than leave a second
vocabulary pretending to be live.

## Scope

- Delete `cycle_explore_mode` and `EXPLORE_MODES` if nothing else needs them.
- Update/remove `tests/test_explore.py::test_cycle_explore_mode_and_decision_lines`
  — keep pins that still cover `format_explore_decision_lines` / mapfill+stardock
  (already covered by `test_explore_decision_lines_wire.py`); drop cycler-only
  asserts.
- Refresh the `ARMABLE_INTENTS` comment so it no longer points at a live
  `cycle_explore_mode` symbol.
- Do **not** delete `plan_find_formations` or the `formations` branch inside
  `format_explore_decision_lines` (future WIRE when catalog ports).
- Suite green · live `n/a`.

## Constraints

- RETIRE only the cycler (+ its exclusive test surface). No Play/`app.py`
  behavior change. #218 frozen. No §A.2 / new deps.
- Lead-seat only.

## Accept

1. `cycle_explore_mode` / `EXPLORE_MODES` gone from product tree.
2. No product caller regression (Play intent cycle unchanged).
3. Suite green · live `n/a`.

## Proof

```bash
pytest -q tests/test_explore.py tests/test_explore_decision_lines_wire.py tests/test_play_explore_intents.py
pytest -q tests
```

## Disposition

Closes unused-code tip **RETIRE** for `tw2002_aiclient.explore:cycle_explore_mode`.
