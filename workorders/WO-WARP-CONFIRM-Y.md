# WO-WARP-CONFIRM-Y

**Status:** READY · EXECUTE · CRITICAL · Max live 2026-08-01 · Cursor  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/WARP-CONFIRM-Y`  
**Depends:** `main` ≥ `9b78c57`  
**Blocks:** App-armed explore / trade nav through TWGS avoid-list sectors

## Why (live)

```
Warping to Sector 25913
DANGER! You have marked sector 25913 to be avoided!
Do you really want to warp there? (Y/N)
→ halt_not_drivable   (actually halt_not_drivable:warp_confirm)
```

Explore/trade **initiated** the hop, then `_gate_screen` / `_navigate` only auto-drive `main_command`. `warp_confirm` is a known gate class (not NEVER_AUTO) but has **no Y/N handler** → stall.

## Goal

When App/explore/trade **just sent an intentional sector hop** and the settled screen is `warp_confirm`, answer **`Y`** (complete the hop we chose). Do not leave the operator mid-DANGER.

## Scope

1. **Explore** (`session/sector_explore.py`): nested like fight-toll wire — after `_gate_screen`, if `klass == "warp_confirm"` and this run has an intentional pending hop (last movement send was a sector target), `send_and_confirm("Y", …)` appropriate confirm pattern; clear pending. If `warp_confirm` with **no** intentional hop → `N` or halt (no blind Y).
2. **Trade** (`trade_driver.py` `_navigate`): after sector `_confirmed_send`, if screen is `warp_confirm` → `Y`; else keep HOLD on unexpected screens.
3. Pins: classify fixture + explore (and/or trade) driver pin that warp_confirm after intentional hop sends Y and continues; no intentional hop → no Y (or N/halt). Fixture: `tests/fixtures/warp_confirm_prompt.txt`.
4. This WO on the branch.

## Out of scope

Removing sectors from TWGS avoid list · pathfinder avoid-aware BFS (bank follow-on) · #306 holdings (parked) · haggle.

## Accept

1. Intentional hop + `warp_confirm` → `Y` sent; explore/trade does not halt solely for that class.
2. Pins green; full suite green.
3. Live-prove: prefer safe half if easy; else honest NOT-ATTEMPTED / n/a only if truly offline-only pins — Max already live-repro’d.

## Proof

pytest + STATUS. No self-merge.

## Refs

`classify.warp_confirm` · `sector_explore._gate_screen` · `trade_driver._navigate` · Max paste sector 25913
