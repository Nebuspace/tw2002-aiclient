# WO-BUILD-FIGHTER-AFFORDABILITY-DECISION-ENGINE

**Status:** IN FLIGHT · Cursor · `wo/BUILD-FIGHTER-AFFORDABILITY-DECISION-ENGINE`
**Seat:** `impl-aiclient-cursor`
**Priority:** MED
**Depends:** tip GOALS fighters paint; Class-0 live price capture remains a separate WO
**Gated:** no (recommend/display only) · buy EXECUTE stays Max-gated elsewhere
**Refs:** queue-aiclient.md ~365 · `canon/engine/priority-engine.md` Fighter economics ·
AP-09 `afford_fighters` · `cockpit/goals.py`

## Goal

Port archive spending-priority `afford_fighters()` as a **recommend/display**
producer and wire GOALS' static `"need some"` fallback to real labels. Do **not**
arm purchase sends; do **not** invent a tip `FIGHTER_UNIT_PRICE_CLASS0` default
(price injected / fail-closed `price_unknown`).

## Scope

1. `priority_engine.FighterAffordability` + `afford_fighters` + GOALS label helper.
2. `cockpit/goals.py` — zero fighters → override or affordability label.
3. Pins in `tests/test_fighter_affordability.py` + goals composer updates.
4. Canon tip-honesty rows for #6 / Fighter economics (decision engine present;
   EXECUTE still Planned / Max-GO).
5. This WO file.

## Constraints

- Recommend/display only — no live Class-0 purchase driver.
- Unit price must be injected (`fighter_unit_price` / `fighter_price_class0`);
  never default to the community 100cr hypothesis.
- Explicit-path commits; no secrets; no operator-home paths.

## Accept

1. `afford_fighters(credits=None)` / missing unit price → `price_unknown`.
2. Injected price + enough discretionary → `buy_fighters`; hold quote affordable →
   `upgrade_holds` first.
3. GOALS `fighters_aboard=0` without override paints label from the producer
   (not static `"need some"`).
4. live-prove: `n/a` (offline decision/display; no TWGS arm).

## Proof

```
.venv/bin/python -m pytest -n0 tests/test_fighter_affordability.py \
  tests/test_cockpit_goals.py -q --tb=short
```
