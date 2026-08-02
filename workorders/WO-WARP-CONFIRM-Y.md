# WO-WARP-CONFIRM-Y

**Status:** DONE · origin `35b9bb9` (#307) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/WARP-CONFIRM-Y`  
**Depends:** `main` ≥ `9b78c57`  
**Blocks:** App-armed explore / trade nav through TWGS avoid-list sectors · #308 DEATH-RESPAWN banked until this lands

## Why (live)

```
Warping to Sector 25913
DANGER! You have marked sector 25913 to be avoided!
Do you really want to warp there? (Y/N)
→ halt_not_drivable   (actually halt_not_drivable:warp_confirm)
```

Explore/trade **initiated** the hop, then `_gate_screen` / `_navigate` only auto-drive `main_command`. `warp_confirm` is a known gate class (not NEVER_AUTO) but has **no Y/N handler** → stall.

**REVISE (hub reject of tip `be413ed`):** the first pass answered `Y` on EVERY intentional-hop `warp_confirm`, including the avoid-list DANGER body itself. Live: Max pressed Y on an avoid-marked sector → mines → pod destroyed. The DANGER body means the PLAYER previously marked that sector to avoid — the correct autopilot answer is **`N`** (decline), not `Y`. An ordinary (non-avoid) `warp_confirm` still gets `Y`.

## Goal

When App/explore/trade **just sent an intentional sector hop** and the settled screen is `warp_confirm`:
- **Avoid-list DANGER body** (player previously marked this sector to avoid) → answer **`N`** (decline the hop) and deny-list that sector so this run does not immediately re-pick the same hop.
- **Ordinary confirm** (no DANGER body) → answer **`Y`** (complete the hop we chose), as before.

Do not leave the operator mid-DANGER either way.

## Scope

1. **Shared avoid-detection** (`session/classify.py`): `is_avoid_danger_warp(full_text) -> bool` — True only for TWGS's own avoid-list DANGER body ahead of the `warp_confirm` prompt (anchored on `tests/fixtures/warp_confirm_prompt.txt`'s live shape); False for a bare/ordinary confirm. One owner, imported by both call sites below.
2. **Explore** (`session/sector_explore.py`): nested like fight-toll wire — after `_gate_screen`, if `klass == "warp_confirm"` and this run has an intentional pending hop (last movement send was a sector target): avoid-DANGER → `send_and_confirm("N", …)`, deny-list the declined target sector for this run (`explore.warp_target_for_intent`'s new `deny` kwarg, threaded through `map_fill_warp_target`/`plan_map_fill`/`frontier_edges`/`plan_find_stardock`'s hunt branch) so the next tick doesn't re-offer it; ordinary confirm → `send_and_confirm("Y", …)` as before; clear pending either way. If `warp_confirm` with **no** intentional hop → no auto-answer, ordinary halt stands (unchanged).
3. **Trade** (`trade_driver.py` `_navigate`): after sector `_confirmed_send`, if screen is `warp_confirm` → avoid-DANGER: `N` then `ChainHold(f"avoid_declined:{hop_index}:{next_sector}")` (refuse the hop rather than loop back into the same avoided sector — the chain's route was computed against the known graph, not TWGS's avoid-list); ordinary confirm → `Y` as before. `N` added to `_ALLOWED_LETTER_SENDS`.
4. Pins: classify fixtures (avoid: `tests/fixtures/warp_confirm_prompt.txt`; new plain/non-avoid: `tests/fixtures/warp_confirm_prompt_plain.txt`) + explore + trade driver pins — avoid → `N` (no re-pick / no repeat send); non-avoid → `Y` (unchanged path); no intentional hop → still no auto-answer / ordinary halt. Plus a pure-function `deny` unit pin in `test_explore.py` (`frontier_edges` / `map_fill_warp_target`).
5. This WO on the branch, Accept updated to match the REVISE.

## Out of scope

Removing sectors from TWGS avoid list · pathfinder avoid-aware BFS / rerouting around a denied sector (bank follow-on) · deny-filtering the StarDock known-route / recovery paths (only the fresh-frontier pick is deny-filtered; recovery only ever targets already-known sectors, which an undiscovered avoided sector never is) · #306 holdings (parked) · #308 DEATH-RESPAWN (banked) · haggle.

## Accept

1. Intentional hop + avoid-list DANGER `warp_confirm` → `N` sent; declined sector deny-listed so explore does not immediately re-pick it (trade: `ChainHold`s instead of looping).
2. Intentional hop + ordinary (non-avoid) `warp_confirm` → `Y` sent; explore/trade does not halt solely for that class.
3. No intentional hop + `warp_confirm` → still no blind auto-answer; ordinary halt stands (existing pin).
4. Pins green (avoid→N, non-avoid→Y, no-hop→halt, explore + trade); full suite green.
5. Live-prove: NOT-ATTEMPTED is fine here — Max already live-repro'd the failure mode (avoid→Y→mines→pod destroyed); do not invent live diversity.

## Proof

pytest + STATUS. No self-merge.

## Refs

`classify.is_avoid_danger_warp` · `classify.warp_confirm` · `explore.warp_target_for_intent`'s `deny` kwarg · `sector_explore._gate_screen` · `trade_driver._navigate` · Max paste sector 25913 (original stall) · Max live avoid→Y→mines→pod-destroyed (this REVISE)
