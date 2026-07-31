# WO-CHAINS-LIVE-REFRESH — refresh chain/HUD scalars during/after explore

**Status:** DONE · origin `5767411` (#228) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/CHAINS-LIVE-REFRESH`
**Depends:** `main` ≥ `8f4e6fc` (#227 Gather chrome)

## Goal

Trade Loop Chains / GOALS chain row stop staying empty until the operator
presses `L`. Today `chain_search.recompute` (and `chain_scalars.update`) run
primarily on chains popup open (`app.py` `chains_open`); explore progress does
not keep chain scalars / world_stats fresh mid-run, so the HUD/GOALS look dead
while exploring.

## Symptom (operator)

No Trade Loop Chain visualization / HUD not filling during explore — even after
ports exist. Pressing `L` may populate the modal, but always-on surfaces lag.

## Scope

1. **Budgeted refresh** of `world_stats` (known_sectors) and `chain_scalars`
   during explore progress and/or Play idle poll — throttle OK (do not recompute
   every draw frame; never on the hot draw path).
2. Keep **`L` as the full discovery modal**; discovered rows remain
   display-only / non-armable (never auto-arm).
3. Offline pins: after a fixture explore (or synthetic world with ports),
   scalars update without opening `L`; opening `L` still works and does not
   double-corrupt state.
4. Smallest change that makes GOALS/HUD chain-related rows leave empty during
   normal explore use.

## Out of scope

- Auto-arming discovered chains.
- Full trainer-cockpit canon bubble redesign.
- Draw-write choke guard / ambiguous-width policy (banked separately).
- `#218` app.py split (frozen).
- Flipping explore dock default ON.

## Constraints

- No draw-path recompute (existing discipline: refresh off explore terminal /
  idle poll / explicit events only).
- Throttle/budget recompute cost — `chain_search.recompute` can be expensive.
- Live-prove → Cursor after suite: after Gather explore (`D` then `E`) on ≥1
  host, observe chain scalars / GOALS Map or chain row update without requiring
  `L` first (or honest SKIP if world too empty — then prove post-`L` still works
  and document why live refresh had nothing to show).

## Accept

1. Explore progress or Play idle poll refreshes `known_sectors` / chain scalars
   without opening `L` (offline proof).
2. `L` modal still opens and shows discovered chains; rows not auto-armed.
3. No per-frame draw-path recompute (pin or structural evidence).
4. Full offline `suite` green.

## Proof

- Focused unit/integration tests for refresh trigger + throttle.
- Full offline `suite`.
- **Live: DEFERRED → Cursor** after suite.

## Refs

- Max live-test 2026-07-29 (chains/HUD empty during explore)
- `.samantha/plans/visible-client-gaps-2026-07-29.md`
- `app.py` `chains_open` / explore terminal poll
- `chain_search.recompute` · `chain_status.ChainScalars` · `world_stats.WorldStats`
- #227 Gather chrome (operators can now find dock)
