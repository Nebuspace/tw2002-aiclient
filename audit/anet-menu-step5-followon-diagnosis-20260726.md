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

**Product classify gap for this layout was addressed** by `WO-ANET-BANNER-LAYOUT` (merged earlier today) without inventing a new class — widened title regex + coherent proximity for boxed title. Tip fixture `tests/fixtures/game_select_menu_banner_anet_boxed_title.txt` + `test_anet_boxed_title_banner_game_select_fixture` pin `classify_screen` → `game_select`.

**Honesty bound (CC 18:20:54Z — accepted):** fixture + prior live frame prove the **mislabel mechanism** and that the **boxed-title banner shape** now classifies as `game_select`. They do **not** by themselves prove a-net **NEW** (registration) step5 at current tip — PR #7 live-prove qualified NEW+RETURNING for rogue only; a-net/micro were unqualified. Registration can insert screens a RETURNING login never shows. **NEW path = not directly re-proved this tip.**

**This tip does not invent a screen class and does not re-widen classify.** Live NEW vs RETURNING diff via `proof_anet` under the ephemeral bank is the cheap discriminator (Shell blocked on this seat).

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
- Not live ensure in this STATUS — bank path now known (`/tmp/tw2002-live-ensure-matrix-20260726T0801Z`); Shell no-exit blocked the run on this seat.

---

## Accept shape for this tip

**Diagnosis complete (docs):** mislabel (b) confirmed on prior capture; boxed-title banner classifies as `game_select` at tip via fixture; **no classify invent under 5A**.

**Explicit non-claim:** a-net **NEW** path at tip **not directly re-proved** (fixture ≠ registration step5; PR #7 live-prove did not qualify a-net NEW). Stronger Accept = one live NEW (+ RETURNING) under `TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z` + isolated `TW_RUN_DIR` — hub/Max or Shell recovery. Bank path posted in coord 18:20Z (keys only).
