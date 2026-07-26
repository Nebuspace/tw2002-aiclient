# WO-ANET-STEP5-LIVE-BYTES

**Status:** IN FLIGHT · Cursor · hub-seeded `wo/ANET-STEP5-LIVE-BYTES`  
**Posted:** 2026-07-26 · hub live wave on `7e43af6` falsified “a-net root already fixed”  
**Depends:** tip ≥ `7e43af6` (banner + letter on main); ephemeral bank  
**Seat:** Cursor preferred (capture + classify offline); hub may assist live capture if Shell dead

## Goal

Decide why live a-net still fails `menu`@login step5 on a tip that already has `WO-ANET-BANNER-LAYOUT` + game-letter autoselect — **by comparing live step-5 bytes to the committed fixture**, not by re-reasoning.

## The falsification (do not rediscover)

Hub laptop @ `7e43af6`:
- a-net NEW → FAIL `menu`@step5
- a-net RETURNING → FAIL `menu`@step5
- Fixture `tests/fixtures/game_select_menu_banner_anet_boxed_title.txt` still classifies as `game_select`

PR #15’s “(b) mislabel; root already closed by banner WO” is **falsified** for the live ensure path.

## Decisive experiment (Accept core)

1. Capture the **exact** screen bytes `ensure` meets at step 5 under the bank (redacted audit + fixture candidate).
2. Run `classify_screen` on those live bytes.
3. Diff live bytes vs `game_select_menu_banner_anet_boxed_title.txt`.

| Live classify | Meaning | Next |
|---|---|---|
| `game_select` | Fixture OK; fault **downstream** of classify (letter send / ensure step) | Diagnose ensure path — still no invent class |
| `menu` (or other) | Fixture **not representative** | Fix classifier/bounds from **live** bytes + new fixture; pin live-derived |

**Do not** treat a green fixture pin as evidence the live path is fixed.

## Scope

- Live capture under bank (isolated run-dir) ± hub assist
- `audit/` redacted note with classify result + diff summary
- Product fix **only** if experiment points there and is evidence-backed
- Optional fixture update from live bytes

**Out:** invent `screen_class` without Max/hub GO · `login.py` / blank-reject (CC) · README · xeno Phase-2 invent

## Accept

1. Live step-5 bytes captured (or honest capture-blocked with why).
2. Classify result on those bytes recorded.
3. Diff vs committed fixture summarized.
4. Either: evidence-backed tip fixing the live path, **or** STATUS that names the failing layer (classify vs downstream) with next WO banked.
5. No “fixture green ⇒ live fixed” claim.

## Proof

Redacted audit + targeted pytest if product changes; hub live-prove on a-net cell after fix. Midstream: classify on captured bytes offline OK.

## Refs

- Hub live wave / matrix: `audit/live-ensure-matrix-reprove-20260726.md`
- CC 2026-07-26T18:57:39Z (experiment design)
- `WO-ANET-MENU-STEP5-FOLLOWON` / PR #15 honesty bound
