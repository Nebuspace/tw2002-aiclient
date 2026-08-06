# WO-CLEANUP-SCREENS-PLAY-SUBTITLE-PLACEHOLDER

**Status:** DONE (pending merge)
**Priority:** LOW
**Gated:** no

## Goal

Remove the unused `PLAY_SUBTITLE` placeholder constant from `screens.py`
(superseded by PWO-051 honest blank GAME grid).

## Scope

- `tw2002_aiclient/screens.py` — delete `PLAY_SUBTITLE` + stale retention comment
- `tests/test_play_chrome_nav.py` — drop unused import; keep `placeholder not in joined` pin
- This WO file

## Accept

1. No product/test reference to `PLAY_SUBTITLE`.
2. `pytest tests/test_play_chrome_nav.py -n0` green.
3. live-prove: n/a (offline chrome constant delete).

## Proof

```
rg PLAY_SUBTITLE tw2002_aiclient tests   # expect 0 hits
.venv/bin/python -m pytest tests/test_play_chrome_nav.py -n0
```
