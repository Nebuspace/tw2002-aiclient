# WO-FIND-STARDOCK-TOGGLE

**Status:** DONE · origin `2497c16` (#316) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/FIND-STARDOCK-TOGGLE`
**Depends:** trainer calm strip (`WO-PLAY-STRIP-TRAINER-CHROME`) · explore intents (`find_stardock` / `map_fill`)

## Why

Explore always hunted StarDock with no chrome control. Max wants a calm
**`F)ind StarDock·ON/OFF`** toggle in the Explore cluster so `E` can map-fill
when the hunt is off.

## Goal

Ship `F)ind StarDock·ON` (default ON) on the teachband; `F` flips it; `E` /
App-armed explore respect it.

## Scope

1. Teachband Explore cluster: `E)xplore  F)ind StarDock·{ON|OFF}  P…  C…  S…`
2. `PlayShellScreen.find_stardock_on` default True; `F`/`f` flips (local chrome).
3. `_start_policy_explore`: ON → `INTENT_FIND_STARDOCK`; OFF → `INTENT_MAP_FILL`
   (both `min_sectors=0`).
4. Reclaim calm `F` from fight-tolls; move fight-tolls opt-in to `X` (still
   unadvertised on the calm strip).
5. Pins + this WO file.

## Out of scope

- Ether-probe / Class-9 shipyard scrape · hold-buy runner · List Loops popup float.

## Accept

1. Default band shows `F)ind StarDock·ON` after `E)xplore`.
2. `F` then `E` starts map-fill; default `E` still find-StarDock.
3. Focused suite green.

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_cockpit_teachband.py \
  tests/test_play_strip_trainer_toggles.py \
  tests/test_play_explore_intents.py \
  tests/test_play_explore_flags.py -q
```
