# WO-BUILD-HAGGLE-PARAMS-REGISTRY

**Status:** IN FLIGHT · Cursor · `wo/BUILD-HAGGLE-PARAMS-REGISTRY`
**Seat:** `impl-aiclient-cursor`
**Priority:** LOW
**Gated:** no (pre-ruled DECISIONS 2026-08-05)
**Refs:** queue-aiclient.md ~372 · `session/haggle.py` · `canon/DECISIONS.md` auto-haggle tuning

## Goal

Move auto-haggle round / threshold / aggression (and related timeouts) out of
silent `session/haggle.py` module literals into an authored registry
(`data/haggle/params.json` + `haggle_params.py`), matching the project's
data-driven-registries preference.

## Scope

1. `tw2002_aiclient/haggle_params.py` — `HaggleParams` + `load_haggle_params`.
2. `data/haggle/params.json` — live-proven defaults (verified_vs_live=true).
3. `session/haggle.py` — default kwargs sourced from the registry.
4. `tests/test_haggle_params.py` + existing haggle suite still green.
5. This WO file.

## Constraints

- No behavior change at the live-proven defaults (4 / 5% / 15%).
- Per-call kwargs on `run_haggle` remain overrides.
- No money-path / default-ON change (`TradeDriverConfig.auto_haggle` stays False).
- Explicit-path commits; no secrets; no operator-home paths.

## Accept

1. `load_haggle_params()` returns round_cap=4, accept=5.0, aggression=15.0.
2. `session.haggle` `_DEFAULT_*` aliases equal `DEFAULT_HAGGLE_PARAMS`.
3. Existing `tests/test_haggle.py` still passes unchanged.
4. live-prove: **n/a** (offline params substrate; no TWGS arm).

## Proof

```
.venv/bin/python -m pytest -n0 tests/test_haggle_params.py tests/test_haggle.py -q
```
