# WO-AUDIT-BUILD-SHIPPROG-FOCUS-OVERLAY-BRIDGE

**Status:** CLAIMED by `impl-aiclient-cursor` (hub HEADS-UP next-pick 2026-08-04T16:47:44Z)
**Priority:** MED
**Depends-on:** AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP (landed)
**Gated:** no — status/ranking only; no send/arm

## Goal

Bridge Layer-B `game_data` catalog booleans onto `status` and apply the canon
boolean-weight overlay so unmet ship/hold price prerequisites raise explore in
FOCUS and `⊘`-gate upgrade until quotes exist.

## Scope

- `tw2002_aiclient/game_data_stats.py` (new) — off-draw refresh + merge
- `tw2002_aiclient/focus_status.py` — weight overlay sort + upgrade gates
- Wire: `screens.py`, `app.py` status wrap, `cockpit/live_refresh.py`
- `tests/test_focus_status.py`, `tests/test_game_data_stats.py`
- `tests/test_status_vocabulary_guard.py` — drop starved allowlist entries
- `canon/engine/priority-engine.md` — overlay bridge honesty flip
- This WO file

## Out of scope

- Full 13-objective priority kernel (RT / stay-vs-leave)
- TW-22 auto-max-holds / purchase execute
- Live TWGS crawl/send

## Accept

1. StarDock known + empty/missing catalog on status → explore sorts above chain EV; upgrade `gated` with ship/hold reason; composer shows `⊘`.
2. `ship_prices_count > 0` + hold label → those gates clear; EV ranking resumes.
3. `GameDataStats` merges from persisted `game_data` (capture producer); starve-guard updated.
4. No send/arm from this path.
5. live-prove: `n/a` (status/ranking only).

## Proof

`pytest tests/test_focus_status.py tests/test_game_data_stats.py tests/test_status_vocabulary_guard.py` + suite green. STATUS with SHA.

## Refs

- `canon/engine/priority-engine.md` § Boolean-weight overlay (~166–183)
- queue-aiclient.md `AUDIT-BUILD-SHIPPROG-FOCUS-OVERLAY-BRIDGE`
