# WO-TEST-STARDOCK-HOLD-PLAN-AT-MAX-COVERAGE

**Goal:** Exercise the "ship already at max cargo holds" screen at the plan/driver layer, not just at parse/classify — proving TW-22 auto-max refuses to fire at the ceiling and the one-pass driver refuses to send when no qty prompt is on screen.

**Context:** `tests/fixtures/stardock_cargo_hold_quote_at_max.txt` is consumed by `test_introspector.py` (`parse_cargo_hold_price` → `None`) and `test_classify.py` (screen recognition), but `stardock_hold_plan.py` (`parse_hold_qty_range`, `parse_hold_unit_price`, `compute_auto_max_qty`, `plan_from_status(..., auto_max=True)`) and `stardock_hold_driver.py` (`run_hold_purchase`) never see this fixture/scenario. `_autonomy_auto_fire` (app.py) relies on `plan_from_status(...) is None` to skip auto-fire at the ceiling — that fail-closed path had no direct test.

**Scope (owned paths):**
- `tests/test_stardock_hold_plan.py`
- `tests/test_stardock_hold_driver.py`
- This WO file

**Constraints:**
- Test-only; no product code changes unless a real hole blocks the test (none found — existing fail-closed behavior already covers the ceiling case).
- Do not expand into purchase-driver scope beyond proving the at-max refusal path.
- live-prove `n/a` (offline unit tests only).

**Accept:**
1. `parse_hold_qty_range` / `parse_hold_unit_price` return `None` on the at-max fixture text (no range/price line present when already at ceiling).
2. `compute_auto_max_qty` and `plan_from_status(..., auto_max=True)` refuse (return `None`) when evidence reflects the ceiling (empty holds = 0), matching `_autonomy_auto_fire`'s `plan is None` skip.
3. `run_hold_purchase` refuses with `unknown_qty_range` when driven against the at-max screen text (defense-in-depth at the driver layer).
4. `pytest tests/test_stardock_hold_plan.py tests/test_stardock_hold_driver.py` green; full suite green.

**Proof:** pytest output (targeted + full suite) in STATUS with SHA.

**Refs:** `tw2002_aiclient/stardock_hold_plan.py` · `tw2002_aiclient/stardock_hold_driver.py` · `tw2002_aiclient/app.py` (`_autonomy_auto_fire`) · `tests/fixtures/stardock_cargo_hold_quote_at_max.txt` · `canon/strategy/ship-progression.md` § Coded auto-max-holds (TW-22).
