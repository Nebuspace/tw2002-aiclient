# WO-PRIORITY-ENGINE-KERNEL — Un-park the full 13-objective priority-engine kernel (P6 gold-prize close)

> Status: READY — hub un-parks Option B (2026-08-05, Max directive: "push aiclient towards Phase 6 full autopilot")
> Refs: `canon/engine/priority-engine.md` (full doc, esp. §"13-objective priority catalog" · §"round-trip (RT) travel-cost model" · §"Boolean-weight overlay") · `WO-GAP-PWO-088-HONESTY.md` (prior hub GO Option A+C, explicitly deferred Option B) · `WO-P6-080-088-autopilot-PREP.md` (P6 tip inventory — this WO is the sole missing P6 item)

## Why now

P6 ("APP autopilot + rule engine") is 8 of 9 items LIVE on tip (PWO-080…087 confirmed live per the
PREP inventory's own tip table). PWO-088 ("priority engine ranks taught only") is the one
DONE/PARTIAL row: the Layer-2 FOCUS display ranker (`focus_status.recommend_focus_candidates` +
`game_data_stats.GameDataStats`) is live and correctly labeled Layer-2-only per
`WO-GAP-PWO-088-HONESTY`'s docs-only closure. The full kernel — the 13-objective catalog's RT
(round-trip travel-cost) model and stay-vs-leave EV feeding the live sort key — was deliberately
parked as "hub Option B, not built" at that time. This WO un-parks it: it is the single remaining
gap between P6's current state and a genuinely complete priority-driven autopilot.

## Goal

Wire the already-designed (and partly already-coded) RT/stay-vs-leave math into the live FOCUS sort
key so unmet weight-100…40 objectives actually outrank action-EV suggestions per
`canon/engine/priority-engine.md`'s documented `(0, weight)` / `(1, action_ev)` / `(0, weight ×
(1−progress))` overlay — not just the current catalog-boolean-gate-only behavior.

## Scope

Per the canon doc, the underlying primitives already exist and are cited live:
- `priority_engine.travel_cost_rt_turns(hops_out, hops_return, turns_per_warp)` (RT cost)
- `priority_engine.stay_vs_leave_upgrade()` (v0 stay-vs-leave EV comparison)
- `hops_of_path()` / `compute_return_path()` / `explore.path_to_sector()` (route inputs)
- `MIN_CHAIN_LINKS_TO_EXECUTE` / `CHAIN_LINKS_PREFER_SEARCH_BELOW` / `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE`

Disjoint sub-parts for a subagent-worker build-wave (name file-lanes so workers don't collide):

1. **Sort-key wiring lane** (`tw2002_aiclient/focus_status.py`, `tw2002_aiclient/priority_engine.py`)
   — replace the current catalog-boolean-only gate with the full `(0, weight)` / `(1, action_ev)` /
   `(0, weight × (1−progress))` sort key from the canon table; wire the pre-flight checklist (5
   conditions, priority-engine.md §"Pre-flight checklist") as the gate on offering an upgrade
   suggestion above a running chain.
2. **RT/stay-vs-leave live-bridge lane** (`tw2002_aiclient/priority_engine.py`, ship/catalog
   introspection call sites) — bridge `stardock_route` / `ship_catalog` (currently "Planned — live
   bridge Planned" per catalog row #2/#4/#5 in the canon table) so RT cost and stay-vs-leave EV run
   on live data, not just unit-test fixtures. **Fail-closed on unknown route/catalog data** — never
   invent a hop count or price (canon: "Distances are never guessed").
3. **Test + honesty lane** (`tests/`, `canon/engine/priority-engine.md`) — update the canon Status-
   in-code column per row once each objective's writer lands (mirror the existing 2026-08-04 honesty-
   pass pattern for rows 1/3); do not claim "Implemented" for a row whose writer is still missing —
   state which side (reader/writer) is present, same discipline as the existing column.

## Constraints

- **Never upstream of stop-on-unknown.** The ordering this engine produces is consumed strictly
  downstream of the run-loop's screen-recognition halt — an unrecognized screen always wins over any
  computed EV, full stop (canon, load-bearing boundary table row 1).
- **The engine emits an ordering, not an action.** It never fires a keystroke itself — only `{app,
  human}` ever send, and the app only on a recognized screen (existing hard rule, unchanged by this
  WO).
- **No invented defaults / no guessed distances.** Unknown route or catalog data fail-closes the
  candidate (existing rule, echoed above) — do not backfill a plausible-looking number to unblock a
  ranking.
- **Genesis/fighter-buy EXECUTE stays out of scope** — objectives #6 (fighter buy) and #11 (planet
  placement) are explicitly EXECUTE-excluded/human-confirmed-only per the existing canon rows; this
  WO only wires the *ranking*, never adds new EXECUTE surfaces for those two rows.
- Not a safety-list item (core mechanics/design, no auth/payments/MFA/admin/AI-safety/new-deps
  surface) — proceed without further Max sign-off per the standing carte-blanche/push-P6 directive;
  still route any genuinely new EXECUTE-authorizing surface (a live keystroke this ranking would
  newly justify sending) back to `❓ DECISION-NEEDED` if the build reveals one.

## Accept

- Live FOCUS suggestions demote a higher-EV upgrade behind a running trade chain when
  `stay_vs_leave_upgrade()` says "stay," matching canon's documented behavior (currently: sort key is
  catalog-gate-only, doesn't run this comparison).
- At least one previously "Planned — live bridge Planned" catalog row (#2 ship-type, #4 ship-catalog
  cost, or #5 hold-upgrade cost) moves to a live-bridged status with a real reader+writer, cited
  file:line.
- `canon/engine/priority-engine.md`'s "Full 13-objective kernel... remains parked" line (line 195) is
  either removed or rewritten to state the new live scope precisely (no residual overclaim, no
  residual "still parked" understatement once shipped).

## Proof

`rg` for `stay_vs_leave_upgrade` call sites showing it's invoked from the live FOCUS path (not just
tests); before/after FOCUS suggestion ordering on a fixture with a running chain + a cheaper-looking
upgrade, demonstrating the demotion; updated canon Status-in-code cites matching tip.
