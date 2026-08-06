# WO-CLEANUP-SETTLE-PROFILES-DECLARATIVE-TABLE

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** LOW (Cycle-43)  
**Depends-on:** none

## Goal

Promote ad-hoc `send_and_confirm` flags into a named `SETTLE_PROFILES` registry
and `send_and_confirm_for(..., profile=...)`, so warp-awareness / idle-confirm
are selected by profile name. Callers migrate incrementally.

## Scope

- `tw2002_aiclient/session/settle.py` — `SettleProfile`, `SETTLE_PROFILES`,
  `resolve_settle_kwargs`, `send_and_confirm_for`
- `tw2002_aiclient/menu/crawler.py` — first migration (`stable_idle`)
- `tests/test_settle.py` — registry + merge + helper pins
- `canon/architecture/settle-detection.md` — tip-stamp divergence (2)

## Out of scope

- Migrating every caller (login / trade_driver / …) in this PR
- Changing `send_and_confirm` semantics
- Interjection registry (separate WO)

## Accept

1. Named profiles include at least `stable_idle`, `warp_unstable`, `positive_shape`.
2. `send_and_confirm_for` is a thin merge → `send_and_confirm`; unknown profile KeyErrors.
3. Crawler menu-key path uses `profile="stable_idle"`.
4. Canon no longer claims "no screen-keyed profile registry" without tip home.
5. Offline settle tests green.

## Proof

```bash
.venv/bin/python -m pytest tests/test_settle.py -q -n0 -k 'settle_profile or send_and_confirm_for or resolve_settle'
```

Live-prove: **n/a** (offline settle kernel + one caller migrate; no login/play path change intent).
