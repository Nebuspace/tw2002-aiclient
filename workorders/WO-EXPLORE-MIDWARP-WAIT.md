# WO-EXPLORE-MIDWARP-WAIT

**Goal:** Explore must not halt on mid-warp `sector_display` after an intentional hop.

**Refs:** live Cartogra 2026-08-01 — `halt_not_drivable:sector_display` after one send; warp animation progress bars + Sector body before Command classify as `sector_display`; settle debounce can fire between frames.

## Scope
- `session/sector_explore.py`: while `pending_intentional_hop`, treat `sector_display` as wait/continue (same family as intentional `warp_confirm` handling). Still halt on `sector_display` with no pending hop.
- Pin: scripted mid-warp progress → arrival → continue exploring (not halt).
- Out: mode-split (#313), fight-toll, dock cascade.

## Accept
1. Pin green: hop → `sector_display` frames → `main_command` destination → run does not halt with `halt_not_drivable:sector_display`.
2. Bare `sector_display` without a pending hop still halts.
3. Hop send uses `retry_unstable_idle=True` and does not halt on settle `confirm_failed` mid-animation — arrival is the next `main_command`.
4. Live: explore completes ≥2 hops from FedSpace (or honest NOT-ATTEMPTED with suite).

## Proof
suite + live hop survive.

**Live prove (hub 2026-08-01):** Cartogra @ 3rdage — after fix, explore map_fill
`min_sectors=8` completed `distinct_sectors=8` / `sends_issued=8` / `outcome=completed`
(pre-fix: first hop `halt_not_drivable:sector_display`; interim: `confirm_failed` mid-animation).
