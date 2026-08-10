# WO-CLEANUP-SETTLE-PROFILES-CALLER-MIGRATE

**Status:** in flight (impl-aiclient-cursor)
**Priority:** LOW (Cycle-43 READY residual of WO-CLEANUP-SETTLE-PROFILES-DECLARATIVE-TABLE)
**Depends-on:** WO-CLEANUP-SETTLE-PROFILES-DECLARATIVE-TABLE (registry + crawler — tip)

## Goal

Finish the incremental caller migration called out by
`canon/architecture/settle-detection.md` Divergence (2): product send paths
still using raw `send_and_confirm` move onto named
`send_and_confirm_for(..., profile=...)` without changing settle semantics.

## Scope

- `tw2002_aiclient/session/hud_seed.py` — `positive_shape`
- `tw2002_aiclient/session/autoloop.py` — `positive_shape` / `stable_idle`
- `tw2002_aiclient/session/haggle.py` — `positive_shape`
- `tw2002_aiclient/session/login.py` — `positive_shape`
- `tw2002_aiclient/session/sector_explore.py` — `stable_idle` / `warp_unstable`
- `tw2002_aiclient/trade_driver.py` — profile from retry / confirm_prompt
- `canon/architecture/settle-detection.md` — tip-stamp Divergence (2)
- `tests/test_settle_profile_caller_migrate.py` — structural pin
- this WO file

## Out of scope

- Changing `send_and_confirm` semantics / debounce / stability windows
- New settle profiles
- Interjection-registry residuals

## Accept

1. Listed product modules call `send_and_confirm_for` (no bare settle helper at those sites).
2. Profile choice preserves prior kwargs: warp/retry paths → `warp_unstable`; confirm-prompt paths → `positive_shape` (or warp when retry was also set); idle-only → `stable_idle`.
3. Canon Divergence (2) no longer claims callers are still migrating.
4. Focused settle + migrate pins green.

## Proof

```bash
.venv/bin/python -m pytest tests/test_settle.py tests/test_settle_profile_caller_migrate.py -q -n0
```

Live-prove: **n/a** (offline profile routing; no login/play arm intent).
