# a-net `menu`@step5 follow-on — diagnosis (Max 5A)

**WO:** `WO-ANET-MENU-STEP5-FOLLOWON`  
**Seat:** `impl-aiclient-cursor` · branch `wo/ANET-MENU-STEP5` @ tip base `8d8b1d6`  
**Ruling:** Max **5A** — capture-first investigation; **no new `screen_class` invent**  
**Date:** 2026-07-26

No passwords, handles, or live screen dumps in this file.

---

## Verdict

| Candidate | Status |
|---|---|
| (a) remote login stall (host stuck mid-paint) | **Ruled out** for the durable a-net NEW fail — settle discriminator A==B==C (prior capture) |
| (b) game-select ↔ `menu` **mislabel** | **Confirmed** — prior live frame + direct `classify_screen` call |
| (c) ensure-step expectation mismatch alone | **Secondary** — ensure stagnates because login has no rule for "menu that is the door"; root is (b) |

**Product classify gap for this layout was already closed** by `WO-ANET-BANNER-LAYOUT` (merged earlier today) without inventing a new class — widened title regex + coherent proximity for boxed title. Tip fixture `tests/fixtures/game_select_menu_banner_anet_boxed_title.txt` + `test_anet_boxed_title_banner_game_select_fixture` pin `classify_screen` → `game_select`.

**This tip does not invent a screen class and does not re-widen classify.** Remaining Accept gap: optional **live** re-ensure on a-net NEW at current tip (N-of-M) — blocked here on Shell + no coord-posted ephemeral bank path yet.

---

## Evidence chain (opened, not echoed)

1. **Matrix** (`audit/live-ensure-matrix-20260726.md`): a-net NEW durable FAIL `menu`@step5 = remote.
2. **Stall diagnosis** (`audit/live-ensure-stall-diagnosis-20260726.md` Result 2):
   - Frame = TWGS game-select (version + registered + boxed `Trade Wars 2002 Game Server` + Selection prompt).
   - Direct classify at then-tip: title regex miss (year token) **and** proximity miss (title 13 rows below core banner) → both boxed and banner detectors False → fallthrough `menu`.
   - Rogue control same tip: `game_select` in 1 step (title without year; compact banner).
3. **Hypothesis note** (`audit/a-net-menu-step5-game-select-hypothesis-20260726.md`): correlation only; superseded by (2).
4. **Fix already on `main`:** `WO-ANET-BANNER-LAYOUT` — optional `\d{2,4}` in title; `_twgs_banner_signals_coherent` allows title below on art/box line when core version+registered are compact. Fixture + adversarial pins in `tests/test_classify.py`.

---

## What this WO is **not**

- Not a drive-by proximity ceiling raise (stall note warned; ANET WO used coherent-signal shape instead).
- Not micro `unknown`@step6 (different root — blank-name reject; see same stall doc Result 1 / `WO-MICRO-*`).
- Not live ensure in this STATUS — ask hub for ephemeral bank path in coord if Max wants N-of-M proof at tip.

---

## Accept shape for this tip

**Diagnosis complete (docs):** mislabel (b) confirmed; fix already shipped via ANET banner WO; no further classify invent under 5A.

**Optional follow:** hub/Max live `tw ensure` a-net NEW (+ RETURNING via `proof_anet`) against tip ≥ `8d8b1d6` with `TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z` and an isolated `TW_RUN_DIR` — expect `game_select` then progress past step5 (or honest fail with new redacted frame). Bank path posted in coord 18:20Z (keys only); Cursor Shell no-exit blocked the live attempt on this seat. Not required for docs Accept under 5A.
