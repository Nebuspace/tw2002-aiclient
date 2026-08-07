# WO-CLEANUP-PORT-ECONOMICS-UNUSED-STRATEGIES-PATH

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-PORT-ECONOMICS-UNUSED-STRATEGIES-PATH`
**Priority:** LOW
**Gated:** no

## Goal

`load_coach_port_economics_params` required `strategies.json` only because it
called `load_coach_kb`, which always parses strategies — even though this helper
never uses strategy values (schema check on port-economics keys in `params.json`
only).

## Change

Load + `validate_param` from `params.json` directly. Drop the strategies
dependency.

## Accept

1. Helper no longer opens `strategies.json`.
2. Tip + tmp-path-only params still select `COACH_PORT_ECONOMICS_KEYS`.
3. Missing-key raises unchanged.
4. live-prove: n/a (offline schema helper).

## Proof

```bash
.venv/bin/python -m pytest tests/test_port_economics.py -q -n0
```
