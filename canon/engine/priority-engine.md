---
type: System
title: Priority Engine — The Strategic Layer
description: The deterministic strategic layer that ranks what to pursue and orders which taught behaviors run or which suggestions the human sees — it never picks a live keystroke over an unrecognized screen.
tags: [priority, strategy, ranking, weights, boolean-goals, round-trip-cost, prescriptive, deterministic, stop-on-unknown]
timestamp: 2026-07-23T20:21:02Z
---

The priority engine is the trainer's **strategic layer**: a pure-logic ranker that answers "of the
things worth pursuing, which matters most right now, and in what order?" It scores competing
objectives — is the turn/credit count known yet, has StarDock been found, is there a trade chain long
enough to grind, is a hold upgrade affordable — and produces an ordered list. That list drives three
things and three things only: **which taught behaviors the app is willing to run, in which order; how
the deterministic candidate-miner and the human-invoked teacher rank the proposals they surface; and
what the [trainer cockpit](/surfaces/trainer-cockpit.md) shows the human as a ranked suggestion.**

The one property that separates this concept from the AI-first ranker it was reborn from is absolute:
**this layer ranks and orders; it does not select a live action.** A high computed expected-value can
make a taught behavior sort to the top of the list, but it can never let the app play a keystroke on a
screen the app does not recognize. Stop-on-unknown is owned by the run-loop
([app-autopilot-model](/architecture/app-autopilot-model.md)) and re-validated every cycle; the
priority engine feeds that run-loop an ordering, and the run-loop still halts on the first
unrecognized frame no matter what the ordering said. Ranking is advisory over the *known*; it is never
an override of the escalate-on-unknown contract in
[control-and-escalation](/architecture/control-and-escalation.md).

# Schema

## What this concept owns, and what it does not

| Owns | Does NOT own |
|---|---|
| The 13-objective priority catalog and its weight ladder | The run-loop that orchestrates taught behaviors and stops on the unknown (that is [app-autopilot-model](/architecture/app-autopilot-model.md) — the §22/TW-23 capstone) |
| Boolean-vs-Range goal typing and the "weight dominates until satisfied" rule | The live keystroke send (only `{app, human}` ever send; the app only on a *recognized* screen) |
| The dependency graph (explore is the shared secondary) | The rule/screen-match guards themselves ([rule-macro-engine](/architecture/rule-macro-engine.md)) |
| The round-trip (RT) travel-cost model, the pre-flight checklist, and stay-vs-leave EV | Firing anything — the engine emits an ordering, not an action |
| The boolean-weight overlay sort key, recast as **rule/behavior prioritization** | Human-facing coaching prose ([coaching-engine](/engine/coaching-engine.md) teaches; this ranks) |

The boundary is load-bearing: the ordering this engine produces is consumed **downstream of**
stop-on-unknown, never upstream of it. A computed EV that outranks everything still yields to an
unrecognized screen, because the ranking is only ever read by a run-loop that re-checks the
screen-match each tick and halts on the first frame it cannot classify.

## The 13-objective priority catalog

Each row is one strategic objective the trainer tracks. **Goal type** is **Boolean** (met / not met)
or **Range** (progress toward a target). **Weight** is the design intent for ordering when an
objective is *unmet* — higher numbers dominate the list until satisfied. Weights are a
**prioritization ladder for which taught behavior / suggestion is offered first**, not a per-cycle
action score that competes against a live screen.

The **Status in code** column below was re-audited against the tree on 2026-07-28 by
`WO-GOALS-STATUS-VOCABULARY`, and rows 1 and 3 moved from "Implemented" to **Starved**. Both had a
working *reader* and no *writer* — the shape that renders an honest `?` forever while every suite
stays green, because tests supply what the product does not. When updating this column, state which
side is missing: "implemented" describing a consumer alone is how these two rows stayed wrong.

**2026-08-04 honesty pass (`AUDIT-CANON-FIX-STALE-TURNSLEFT-CREDITS-STATUS`):** row 1 is no longer
Starved — `protocol._status_response` emits top-level `turns_left` / `credits` on OUTCOME_READ
(`WO-STATUS-CREDITS` · `WO-HUD-STATUS-BRIDGE`); GOALS renders them when present. Residual: FOCUS
weight-100 gating still does not *require* those scalars before other suggestions (overlay bridge
covers catalog #4/#5, not the turns/credits boolean).

| # | Priority | Type | Weight | Depends on | Status in code (2026-08-04) |
|---:|---|---|---:|---|---|
| 1 | Turns & credit count known | Boolean | 100 | — | **Partial** — writers live: `_status_response` emits `turns_left` + `credits` when sticky OUTCOME_READ (`protocol.py`); GOALS Turns/Credits rows consume them. Still omit-until-read (honest `?` before `I`/`observe_*`). FOCUS does not yet weight-gate on unmet #1. |
| 2 | Current-ship type identified | Boolean | 90 | #1 | Planned — no live current-ship introspection adapter; `ShipSpec`/`PlayerState` exist for scoring but aren't fed live |
| 3 | StarDock located | Boolean | 85 | explore when unknown | **Starved** — the READER is implemented (`explore.find_landmark_sectors()`), the WRITER never was: no code writes `landmarks[]`, so the lookup returns `[]` however much is explored and GOALS can never show `StarDock @…`. Blocked on `WO-WM-LANDMARKS-WRITE` |
| 4 | Cost of other ships known | Boolean | 80 | #3 | Partial — GOALS gated until dock found; catalog not yet on live `WorldSnapshot.ship_catalog` |
| 5 | Cost of cargo-hold upgrades known | Boolean | 75 | #3 | Partial — GOALS gated until dock found; quote via `get_cargo_hold_price()` when captured |
| 6 | Obtain fighters (aboard > 0) | Boolean | 73 | #1 (Class-0 at Sol always reachable) | Partial — GOALS shows aboard count + credit-gated status via `afford_fighters()`; buy EXECUTE Planned |
| 7 | Cost of fighters known | Boolean | 70 | #1 (Class-0 assumed reachable) | Partial — `FIGHTER_UNIT_PRICE_CLASS0 = 100` is a hypothesis placeholder |
| 8 | Purchase additional cargo holds | Boolean | 65 | #5, credits, RT cost | Planned — decision logic in `ship_upgrade_decision.py`; EXECUTE navigation-only |
| 9 | Purchase ship with larger holds | Boolean | 60 | #4, loop economics, RT cost | Partial — `_score_upgrade()` scores holds-only cr/turn; live catalog/loop inputs missing; travel one-way only today |
| 10 | Locate special formation for planet placement | Range | 55 | map exploration | Partial — `formations.py` detects dead-ends/bubbles/one-ways/warp-sinks + `genesis_candidates`; no deploy |
| 11 | Place planet to earn resources | Boolean | 50 | #10 candidate chosen | Planned — genesis deploy excluded from app candidate kinds (human-confirmed one-shot only) |
| 12 | Map 100% of galaxy | Range (→100%) | 45 | — | Partial — GOALS shows `N/total (pct%)`; `explore.known_graph()` + frontier BFS; galaxy size often unknown until mapped |
| 13 | Longest trade-loop chain identified | Range | 40 | ports known | Partial — `chains.longest_profit_chain()`; execute floor ≥2 links; ship hull deferred until ≥4 |
| — | Sector-based threats (mines/fighters) | Boolean | 35 | sector visited | Partial — `world_model` persists per-sector threats; not yet a scorer/guard input |

### Weight dominates until satisfied

The weight column is a strict **prerequisite ordering** for unmet objectives: turn/credit
identification (100) must be resolved before anything else is worth offering, StarDock location (85)
gates the price rows below it, and so on down the ladder. "Dominates" means *sorts first among the
taught behaviors the app is willing to run and among the suggestions the human sees* — it is not a
license to act on an unrecognized screen. An unmet weight-100 objective sorting to the top means the
app offers (and a human can approve) the taught "send `I` to learn turns/credits" behavior first; it
never means the app improvises a keystroke to satisfy the goal.

## Dependency chains — explore is the shared secondary

Some objectives can only be reached through another. To learn ship prices you must first find
StarDock; to find StarDock (when its sector is unknown) you must explore. The catalog encodes this as
a graph:

```
turns/credits known
  └─ ship type known
       └─ StarDock located ──(requires explore when unknown)── map fill
            ├─ ship prices known
            └─ hold-upgrade price known
                 └─ purchase hold / buy bigger ship
                      └─ run a trade chain (a taught, human-armed repeating macro)
```

**Explore is the shared secondary for every objective that needs unknown map data** — StarDock hunt,
port discovery, formation survey, chain-edge mining all reduce to frontier hops until the prerequisite
boolean flips. Reborn correction: explore is a *taught, turn-budget-respecting behavior that STOPS on
any unrecognized sector screen*, not a "never idle, keep driving" appetite. See
[exploration-policy](/strategy/exploration-policy.md) for the frontier/BFS mechanism and the retirement
of the never-idle framing.

## The round-trip (RT) travel-cost model

Knowing *what* to pursue is not the same as knowing it is *affordable to pursue right now*. "StarDock
found" (a boolean) does not mean "cheap enough to abandon this trade chain, warp to the dock, buy, and
warp back." Executing any objective costs **turns to reach the action and return to the interrupted
work** — and that return leg is exactly what a one-way path length omits.

**RT turn cost** (current hull) is:

```
travel_cost_rt ≈ (hops_to_dock + hops_to_chain_start) × turns_per_warp
```

`priority_engine.travel_cost_rt_turns(hops_out, hops_return, turns_per_warp)` computes this;
`hops_of_path()` converts an inclusive sector path to a hop count; `compute_return_path()` /
`explore.path_to_sector()` supply the return leg. Distances are **never guessed** — an unknown route
fail-closes the candidate rather than inventing a hop count.

### Pre-flight checklist — before abandoning a live chain for StarDock

All five must hold before an upgrade behavior is allowed to outrank a running trade chain in the
ordering. None of this authorizes a live keystroke on an unknown screen — it only decides whether the
*upgrade suggestion* is offerable and how it sorts.

1. **Target ship + price known** — an introspected catalog row with `cost > 0` (`ship_catalog`; live
   bridge Planned).
2. **One-way path to StarDock known** — `stardock_route` with `len > 1`, or at-dock (`len == 1`);
   unknown route fail-closes (`upgrade: path to StarDock unknown`).
3. **Return path to interrupted work known** → compute `travel_cost_rt`.
4. **Turn budget** — `travel_cost_rt + projected_payback ≤ productive turns`, where
   `productive = turns_left − turn_reserve`.
5. **EV comparison (stay-vs-leave)** — debit the chain profit forgone during RT travel against the
   upgrade's incremental gain after RT + payback; **stay trading** if the chain wins.

### Stay-vs-leave EV

`priority_engine.stay_vs_leave_upgrade()` encodes step 5 (v0): the chain's forgone profit is
`chain_cr_per_turn × travel_cost_rt`; the upgrade's gain is
`upgrade_extra_cr_per_turn × (productive − travel_cost_rt − payback)`; leave only when the gain
strictly exceeds the forgone amount, else stay. When the verdict is "stay," `recommend_actions()`
demotes the upgrade below the running chain in the ordering even if raw upgrade EV was higher — the
ordering respects the interrupted-work cost, not just the headline cr/turn.

### Chain execute-floor thresholds (ordering inputs)

The link count is `len(ProfitChain.hops)` (a closed cycle; a 2-hop back-and-forth or a
three-sector / two-edge path is the smallest chain). These constants are **inputs to which taught
behavior is offerable and how it sorts**, not autonomous triggers:

| Constant | Value | Effect on the ordering |
|---|---:|---|
| `MIN_CHAIN_LINKS_TO_EXECUTE` | 2 | Below 2 links, the run-chain behavior is not offerable — discovery/explore ranks above it |
| `CHAIN_LINKS_PREFER_SEARCH_BELOW` | 2 | Empty hunt-before-grind band: at ≥2 links, prefer earning (fighters/holds) over hunting a longer chain |
| `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE` | 4 | Ship-hull upgrade stays deferred below 4 links so a short chain funds fighters + holds first |

See [trade-loops](/strategy/trade-loops.md) for the loop/chain definitions and the hop-count-then-cr/turn
rank, and [ship-progression](/strategy/ship-progression.md) for holds-first upgrade economics.

## Boolean-weight overlay — recast as rule/behavior prioritization

The design intent is to merge Layer 1 (goal status) and Layer 2 (action EV) with a single sort key so
that an unmet high-weight prerequisite outranks a continuous cr/turn score. **Reborn recast:** this
sort key orders *which taught behavior or suggestion is offered first*; it does **not** let a computed
EV "beat" a live action, and it never applies to an unrecognized screen (there, the run-loop stops —
full stop).

| Goal state | Sort key | Meaning |
|---|---|---|
| Boolean unmet | `(0, weight)` | Prerequisite behavior sorts above any action EV until satisfied |
| Boolean met | `(1, action_ev)` | Normal cr/turn ranking of taught behaviors resumes |
| Range goal | `(0, weight × (1 − progress))` | Partial credit keeps it visible but below hard blockers |

The overlay bridge is **built** (`focus_status.recommend_focus_candidates` +
`game_data_stats.GameDataStats`): catalog booleans from Layer-B `game_data` merge onto
`status`, unmet prerequisites raise explore via `(0, weight)` and gate upgrade with `⊘`
until ship/hold quotes exist. Full 13-objective kernel (RT / stay-vs-leave) remains parked.

## Two-layer information architecture

The strategic layer renders in the cockpit as two related-but-distinct panels. Both are **read-only
context or suggestion** — neither is an autonomous selector.

**Layer 1 — GOALS (informational prerequisite status).** The left-gutter GOALS section
(`GoalsSnapshot` → `compose_primary_goals_lines()`) renders each strategic prerequisite on its own
line with status glyphs: `✓` known/met, `·` in progress / partial, `?` unknown. Turns, credits,
StarDock, map, formations, chain, ship prices, hold price, fighters. This layer does **not** pick an
action; it tells the human (and the future overlay) what is known.

**Layer 2 — FOCUS (ranked candidate behaviors = suggestions).** The FOCUS section below GOALS shows
the priority engine's ordered candidates for the current tick
(`compose_priorities_lines()` → `recommend_actions()`), ranked by comparable cr/turn with gated
candidates carrying `⊘` and a reason. Reborn reframe: **FOCUS is a ranked list of suggestions, not the
app's chosen action.** It says "here is what would be worth doing, in order"; whether a taught behavior
actually runs is gated by human-arming and by stop-on-unknown at the run-loop, not by FOCUS's top row.
Readable labels map `run_chain` → "Trade chain," `upgrade` → "Upgrade," `explore` → "Explore."

## Fighter economics

Fighters (objective #6, weight 73) are gated by **credits**, never by location: the Class-0 port at
Sol (sector 1) is the game-start sector and is **always reachable**, so `⊘ need StarDock` must never
gate this row. `afford_fighters()` reserves the trade float (working capital) first, then prefers a
hold upgrade (weight 75) over a fighter buy (73) when a hold quote is known and affordable, then buys
fighters if discretionary credits cover the stack. Every `None` input fail-closes to `price_unknown`
rather than guessing.

`FIGHTER_UNIT_PRICE_CLASS0 = 100 cr` per fighter is a **[hypothesis] placeholder** — sourced from
community guides, UNVERIFIED against the live game; treat it as configurable until confirmed by an
introspected Class-0 port screen.

> **Verification status:** UNVERIFIED (hypothesis). `FIGHTER_UNIT_PRICE_CLASS0 = 100 cr/fighter`,
> `FIGHTER_SMALL_STACK = 5`, the chain-link thresholds (2 / 2 / 4), and the weight ladder values
> (100→35) are design/placeholder numbers, not confirmed live-server facts. All are configurable and
> must be verified against introspected live screens; author portable semantics, never hardcode
> per-server stat values as truth.

# Code divergences (DOCS WIN — recorded, not silently conformed)

The reborn target is: the priority engine **ranks/orders**; it never selects a live keystroke, and the
run-loop re-validates the screen-match every cycle and stops on the first unrecognized frame. Current
code diverges in these specific ways — recorded here so the divergence is visible, not erased:

1. **`autopilot.select()` is a per-cycle EV action-picker.** `twclient/autopilot.py` scores
   `run_chain` / `upgrade` / `explore` "from scratch, every tick" and picks the highest EV
   (`ranked = sorted(candidates, key=ev_per_turn, reverse=True); chosen = ranked[0]`), then live-sends
   one keystroke. This is the AI-first "compute EV and drive" shape; the reborn model wants the
   ordering to feed a taught-behavior run-loop that stops on the unknown, not a per-tick EV selector
   that assumes the next screen is drivable. The run-loop half of this divergence is recorded in
   [app-autopilot-model](/architecture/app-autopilot-model.md).

2. **`priority_engine.recommend_actions()` is consumed as a live per-tick override.**
   `autopilot.select()` calls `_priority_engine_focus_kind(...)` and, when the engine's focus disagrees
   with the raw-EV winner, reorders and drives that kind live (`reason_prefix = "priority engine"`).
   The reborn role of `recommend_actions()` is to *order taught behaviors and suggestions*, read
   downstream of stop-on-unknown — not to pick the live keystroke for the current tick.

3. **`EXPLORE_BASELINE_EV = 0.01` encodes a "never idle" appetite.** `autopilot._score_explore()`
   emits a fixed tiny baseline EV "so the client never idles when a frontier hop exists." The reborn
   vision retires never-idle keep-driving: explore is a taught, human-armed, turn-budgeted behavior
   that STOPS on any unrecognized sector screen, and depletion/exhaustion is a **STOP-and-escalate**
   guard, not a reason to keep driving. `recommend_actions()` still accepts `explore_baseline_ev` as a
   parameter; its use as an auto-driver justification is the divergence. Recast lives in
   [exploration-policy](/strategy/exploration-policy.md).

4. **`trade_driver.run_chain()` is an autonomous whole-loop chain runner.**
   `twclient/trade_driver.py`'s `run_chain()` drives an entire profit-chain from start to end
   synchronously in one call, routed from a chosen `run_chain` candidate. It is interruptible
   (halts within one send-step of a stop signal) and fail-closed-armed (requires an explicit arm
   token), which is the right safety shape — but a chain "runner" that plays the whole loop is a
   run-loop/behavior-execution concern, and its stop-on-unknown re-validation and human-arm contract
   are owned by [app-autopilot-model](/architecture/app-autopilot-model.md), not by this ranking layer.

5. **The §22/TW-23 run-loop capstone is re-homed.** The autonomous goal-orchestrator run-loop (the
   ASSESS→SELECT→EXECUTE→RECORD tick loop, §22/§23 Phase 1) is described in `autopilot.py`'s module
   docstring as living with the scorer. In the reborn map it **moves to
   [app-autopilot-model](/architecture/app-autopilot-model.md)**; this concept keeps only the
   ranking/ordering half. Do not re-file the control-runtime / stop-on-unknown concern here.

# Citations

- **Reimagined from / folded:** root `priority_engine.md` + `USERDOCS/priority_engine.md` (priority
  catalog, weight ladder, RT travel-cost model, two-layer IA) — content lives here; root file deleted
  (Max GO 2026-07-25). Re-rooted in the reborn vision; the §22 capstone framing retired to
  app-autopilot-model, the never-idle framing retired.
- **Grounded in code:** `twclient/priority_engine.py` (`recommend_actions()`, `stay_vs_leave_upgrade()`,
  `travel_cost_rt_turns()`, `afford_fighters()`, the chain-link + fighter constants);
  `twclient/autopilot.py` (`select()`, `_score_chain/_upgrade/_explore()`, `EXPLORE_BASELINE_EV`,
  `_priority_engine_focus_kind()`); `twclient/chains.py` (`ProfitChain`, `rank_chains()`,
  `longest_profit_chain()`); `twclient/explore.py` (`known_graph()`, `frontier_edges()`,
  `path_to_sector()`, `plan_map_fill()`); `twclient/ship_upgrade_decision.py` (`ShipSpec`,
  `LoopEconomics`, decision engine); `twclient/trade_driver.py` (`run_chain()` whole-loop runner).
- **Cross-links:** [north-star](/architecture/north-star.md) (the strategic layer within the reborn
  vision), [app-autopilot-model](/architecture/app-autopilot-model.md) (consumes this ordering; never
  lets it pick a live action over an unknown screen — owns the run-loop and the §22 capstone),
  [rule-macro-engine](/architecture/rule-macro-engine.md) (this ordering prioritizes rules),
  [control-and-escalation](/architecture/control-and-escalation.md) (the ordering never overrides
  stop-on-unknown), [world-model](/engine/world-model.md) (StarDock/threat/graph state feeding the
  catalog), [trade-loops](/strategy/trade-loops.md), [port-economics](/strategy/port-economics.md),
  [exploration-policy](/strategy/exploration-policy.md), [toll-and-defense](/strategy/toll-and-defense.md),
  [planet-colonization](/strategy/planet-colonization.md),
  [special-formations](/strategy/special-formations.md), [ship-progression](/strategy/ship-progression.md),
  [coaching-engine](/engine/coaching-engine.md).
