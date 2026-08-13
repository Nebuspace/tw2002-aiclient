# WO-CLEANUP-ACTION-SAFETY-ALL-COVERAGE-LEDGER-STALE

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Retire `action_safety.all_coverage()` — zero product callers; `app.py` uses
`assert_coverage_map_intact()` over `COVERAGE` directly. Tests iterate `COVERAGE`.

## Accept

- `all_coverage` gone; tests use `COVERAGE`.
- Product boot path unchanged (`assert_coverage_map_intact`).
- Hub: flip unused-code-disposition.json WIRE verdict if still citing this wrapper.

## Proof

```bash
.venv/bin/python -m pytest tests/test_action_safety_coverage.py tests/test_action_safety_startup_wire.py -n0 -q
rg -n 'all_coverage' tw2002_aiclient tests
```

live-prove: n/a (offline cleanup).
