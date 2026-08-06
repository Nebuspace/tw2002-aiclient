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
| FOCUS → confirm offer selection (`autonomy_policy.choose_offer`) | Live sends / arm confirm chrome (play loop + [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md)) |

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

**2026-08-04 honesty pass (`AUDIT-CANON-FIX-STALE-STARDOCK-LANDMARK-STATUS`):** row 3 is no longer
Starved — `WO-WM-LANDMARKS-WRITE` landed; `world_model.add_landmark` is called from
`sector_explore` on StarDock recognition, and `world_stats.WorldStats` merges `stardock_sectors` /
`stardock_found` onto status for GOALS.

| # | Priority | Type | Weight | Depends on | Status in code (2026-08-04) |
|---:|---|---|---:|---|---|
| 1 | Turns & credit count known | Boolean | 100 | — | **Partial** — writers live: `_status_response` emits `turns_left` + `credits` when sticky OUTCOME_READ (`protocol.py`); GOALS Turns/Credits rows consume them. Still omit-until-read (honest `?` before `I`/`observe_*`). FOCUS does not yet weight-gate on unmet #1. |
| 2 | Current-ship type identified | Boolean | 90 | #1 | **Partial (live-bridged)** — writer: `introspector.parse_current_ship_info` + `Session.observe_current_ship` from `I` ship-info; status emits `ship_type` / `current_ship` omit-until-known. `ShipSpec` for upgrade scoring via `ship_spec_from_current_info` only when a Layer-B catalog row matches (cost/shields never invented from I-info alone). |
| 3 | StarDock located | Boolean | 85 | explore when unknown | **Implemented** — writer: `world_model.add_landmark` from explore (`sector_explore`); reader: `explore.find_landmark_sectors` + `WorldStats` → `stardock_sectors`/`stardock_found`; GOALS paints `StarDock @…` when present. Empty landmark scan still omits keys (honest `?`), never invents `stardock_found=False`. |
| 4 | Cost of other ships known | Boolean | 80 | #3 | **Partial (live-bridged)** — writer: `GameDataStats.refresh` loads Layer-B `game_data` ships and merges `ship_catalog` (`[{ship_name, cost}, …]` for `cost > 0`) plus `ship_prices_count` onto status (`game_data_stats.py`); readers: GOALS + FOCUS overlay + priority-engine pre-flight. Still omit-until-load (no invent). |
| 5 | Cost of cargo-hold upgrades known | Boolean | 75 | #3 | Partial — GOALS gated until dock found; quote via `get_cargo_hold_price()` when captured |
| 6 | Obtain fighters (aboard > 0) | Boolean | 73 | #1 (Class-0 at Sol always reachable) | Partial — GOALS paints `fighters_aboard` + optional `fighter_buy_status` string (`goals.py`); **no** tip `afford_fighters()` module and **no** buy EXECUTE (still Planned / Max-GO) |
| 7 | Cost of fighters known | Boolean | 70 | #1 (Class-0 assumed reachable) | Partial — canon still names `FIGHTER_UNIT_PRICE_CLASS0 = 100` as an **UNVERIFIED hypothesis**; tip Python has **zero** references to that constant (no producer for a numeric price yet) |
| 8 | Purchase additional cargo holds | Boolean | 65 | #5, credits, RT cost | Planned — decision logic in `ship_upgrade_decision.py`; EXECUTE navigation-only |
| 9 | Purchase ship with larger holds | Boolean | 60 | #4, loop economics, RT cost | Partial — `_score_upgrade()` scores holds-only cr/turn; live catalog/loop inputs missing; travel one-way only today |
| 10 | Locate special formation for planet placement | Range | 55 | map exploration | Partial — `formations.py` detects dead-ends/bubbles/one-ways/warp-sinks + `genesis_candidates`; no deploy |
| 11 | Place planet to earn resources | Boolean | 50 | #10 candidate chosen | Planned — genesis deploy excluded from app candidate kinds (human-confirmed one-shot only) |
| 12 | Map 100% of galaxy | Range (→100%) | 45 | — | Partial — GOALS shows `N/total (pct%)`; `explore.known_graph()` + frontier BFS; galaxy size often unknown until mapped |
| 13 | Longest trade-loop chain identified | Range | 40 | ports known | Partial — `chains.longest_profit_chain()`; execute floor ≥2 links; ship hull deferred until ≥4 ([Chain execute-floor thresholds](#chain-execute-floor-thresholds-ordering-inputs) · `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE=4` — short chains fund fighters + holds first; see also [trade-loops](/strategy/trade-loops.md) § thresholds) |
| — | Sector-based threats (mines/fighters) | Boolean | 35 | sector visited | Implemented — `world_model` persists threats; `route_hazard_for_hop` STOPs / path-excludes on known mines or fighter presence (WO-AUDIT-BUILD-SECTOR-THREAT-FIGHTERS-GUARD-INPUT) |

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

1. **Target ship + price known** — an introspected catalog row with `cost > 0`
   (`status["ship_catalog"]` via `GameDataStats` / Layer-B `game_data`; live-bridged).
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
until ship/hold quotes exist. **RT / stay-vs-leave** is live on the FOCUS path
(`priority_engine.upgrade_gate_while_chaining` ← `stay_vs_leave_upgrade` /
`travel_cost_rt_turns`): while an executable chain is present, upgrade is fail-closed
without known StarDock/return hops + economics, and demoted (gated) when stay-vs-leave
says stay — even if headline upgrade EV is higher. Remaining catalog rows (#2 ship-type
writer, #5 hold-quote beyond label, #6–#13 EXECUTE surfaces) stay Partial/Planned per
the Status column; this WO does not invent those writers.

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

## Autonomy offer selection (FOCUS → confirm)

Between FOCUS's ranked list and a live send sits a thin **pure** selector —
`autonomy_policy.choose_offer` — that turns FOCUS candidates into one
operator-facing `AutonomyOffer`. It is **not** a second priority engine and
**not** a live action-picker.

| Owns | Does NOT own |
|---|---|
| Mapping FOCUS candidates → one `AutonomyOffer` (`explore` / `run_chain` / `upgrade` / `idle`) | Ranking weights / EV (that is this concept's Layer 2 / `recommend_*`) |
| Early-game StarDock bias when no ungated trade chain exists | Arming, confirm chrome, or keystrokes (`begin_arm_confirm` / App-armed auto-fire in `app.py`) |
| Gating `upgrade` when hold-arm capability is unknown (`has_hold_arm=False`) | Port Trade / hold auto-fire policy (trainer strip toggles; silent FOCUS `run_chain` auto-fire is refused per explore-vs-trade mode split) |

**Contract.** `choose_offer(status)` reads `status["focus"]["candidates"]` only.
Each candidate must carry `kind ∈ {explore, run_chain, upgrade}` and a bool
`gated`. Broken / missing FOCUS → `idle` with an honest reason. It never
calls adapters, never touches money boundaries, and never invents a kind
FOCUS did not list.

**Selection order (code-grounded).**

1. If no ungated `run_chain` is eligible **and** StarDock is unknown → offer
   `explore` with intent `find_stardock` (early-game bias).
2. Else first ungated eligible candidate (FOCUS order preserved).
3. Else first gated eligible candidate (still confirmable; reason carries
   `gate_reason` or `"preconditions incomplete"`).
4. Else `idle`.

**Consumers.**

- **`O` (offer)** — operator confirm path: `choose_offer` → `begin_arm_confirm`
  → human `y` before any runner starts.
- **App-armed auto-fire** — same selector for Port Trade / Cargo Hold Upgrade
  kinds only; explore stays confirm-gated. Live silent FOCUS trade auto-fire
  is refused; hold upgrade may auto-fire when the strip toggle allows.

Grounded in `tw2002_aiclient/autonomy_policy.py` and the play-loop call sites
in `tw2002_aiclient/app.py`. Cockpit key chrome lives in
`cockpit/autonomy_keys.py` (vocabulary cross-ref deferred —
`AUDIT-CANON-DRAFT-TEACH-BAND-CROSSREF`).

## Fighter economics

Fighters (objective #6, weight 73) are gated by **credits**, never by location: the Class-0 port at
Sol (sector 1) is the game-start sector and is **always reachable**, so `⊘ need StarDock` must never
gate this row.

**Tip honesty (2026-08-04 · `AUDIT-BUILD-FIGHTER-PURCHASE-EXECUTE`):** reborn tip does **not** yet
ship `FighterAffordability.afford_fighters(...)` or a `FIGHTER_UNIT_PRICE_CLASS0` constant in
Python — those names live in this canon (+ archive-port AP-09 narrative) as the *target* spending
priority, not as importable tip symbols. What ships today:

- GOALS (`cockpit/goals.py`) paints `fighters_aboard` and, when present, a free-form
  `fighter_buy_status` string (vocabulary guard still tags that key as needing shipyard-screen
  parsing — not a scored affordability result).
- **Buy EXECUTE** (one-shot Class-0 purchase mirroring `stardock_hold_driver` guard shape) remains
  **Planned** and **Max-gated** until (a) a live/captured Class-0 unit price replaces the hypothesis
  below and (b) Max GO's the money-path arm.

**Target spending priority** (when `afford_fighters` is reborn): reserve the trade float (working
capital) first, then prefer a hold upgrade (weight 75) over a fighter buy (73) when a hold quote is
known and affordable, then buy fighters if discretionary credits cover the stack. Every `None`
input fail-closes to `price_unknown` rather than guessing.

`FIGHTER_UNIT_PRICE_CLASS0 = 100 cr` per fighter remains a **[hypothesis] placeholder** — sourced
from community guides, UNVERIFIED against the live game; treat it as configurable until confirmed by
an introspected Class-0 port screen. **Do not** invent a tip constant that pretends the hypothesis
is measured.

> **Verification status:** UNVERIFIED (hypothesis). `FIGHTER_UNIT_PRICE_CLASS0 = 100 cr/fighter`,
> `FIGHTER_SMALL_STACK = 5`, the chain-link thresholds (2 / 2 / 4), and the weight ladder values
> (100→35) are design/placeholder numbers, not confirmed live-server facts. All are configurable and
> must be verified against introspected live screens; author portable semantics, never hardcode
> per-server stat values as truth.

# Code divergences (DOCS WIN — recorded, not silently conformed)

The reborn target is: the priority engine **ranks/orders**; it never selects a live keystroke, and the
run-loop re-validates the screen-match every cycle and stops on the first unrecognized frame. Where tip
or archive history differs, the gap is recorded here — never silently erased:

1. **Archived `autopilot.select()` per-cycle EV action-picker — do-not-revive.** Pre-rebirth
   `archive/.../twclient/autopilot.py` scored `run_chain` / `upgrade` / `explore` "from scratch, every
   tick" and live-sent the highest EV. That module is **gone from tip** (rebirth cut); there is no live
   import path. Do not "fix the divergence" against dead code — the reborn run-loop contract lives in
   [app-autopilot-model](/architecture/app-autopilot-model.md).

2. **Archived live per-tick override of `recommend_actions()` — do-not-revive.** The same archived
   `autopilot.select()` called `_priority_engine_focus_kind(...)` and could reorder/drive when the
   engine disagreed with raw EV. Tip's ranking role is *order taught behaviors and suggestions*
   downstream of stop-on-unknown — not pick the live keystroke. No tip caller restores that override.

3. **Archived `EXPLORE_BASELINE_EV` auto-driver floor — do-not-revive (tip is suggestion-only).**
   Archive `autopilot._score_explore()` used a fixed tiny baseline EV "so the client never idles."
   Tip may still surface an explore floor as FOCUS suggestion only
   ([app-autopilot-model](/architecture/app-autopilot-model.md)); it must never justify unsupervised
   keep-driving. Recast of explore appetite: [exploration-policy](/strategy/exploration-policy.md).

4. **`trade_driver.run_chain()` arm-gate shape — ADR-003-resolved (not an open divergence).**
   Tip `trade_driver.run_chain()` still drives a whole profit-chain synchronously in one call, but
   the fail-closed arm / interrupt / exclusive-hold contract is **resolved by ADR-003** the same way
   [trade-loops](/strategy/trade-loops.md) and [ship-progression](/strategy/ship-progression.md)
   already record: guarded run only behind `TradeChainRunner` (exact human-confirmed fingerprint,
   daemon re-resolution, one-pass bound, stop/disarm checked at every send). Ownership of the
   run-loop / stop-on-unknown half remains
   [app-autopilot-model](/architecture/app-autopilot-model.md); this ranking layer does not pick or
   rotate chains. Do not re-list the arm-gate as an unresolved priority-engine divergence.

5. **The §22/TW-23 run-loop capstone is re-homed (archive framing only).** The ASSESS→SELECT→EXECUTE→RECORD
   tick loop lived in archived `autopilot.py`'s module docstring. In the reborn map it **lives in
   [app-autopilot-model](/architecture/app-autopilot-model.md)**; this concept keeps only the
   ranking/ordering half. Do not re-file the control-runtime / stop-on-unknown concern here.

6. **Fighter affordability is canon-ahead of tip.** Archive/AP-09 and earlier drafts of this file
   describe `afford_fighters()` + `FIGHTER_UNIT_PRICE_CLASS0` as if tip-imported. Tip Python has
   **zero** hits for those symbols (2026-08-04 tip sweep); GOALS only paints `fighters_aboard` /
   `fighter_buy_status`. The Fighter economics section above records the target priority; buy
   EXECUTE stays Max-gated (`AUDIT-BUILD-FIGHTER-PURCHASE-EXECUTE`).

# Citations

- **Reimagined from / folded:** root `priority_engine.md` + `USERDOCS/priority_engine.md` (priority
  catalog, weight ladder, RT travel-cost model, two-layer IA) — content lives here; root file deleted
  (Max GO 2026-07-25). Re-rooted in the reborn vision; the §22 capstone framing retired to
  app-autopilot-model, the never-idle framing retired.
- **Grounded in code:** tip `tw2002_aiclient/priority_engine.py` / `focus_status.py` (ranking +
  FOCUS suggestion floor); `tw2002_aiclient/autonomy_policy.py` (`choose_offer`, `AutonomyOffer`);
  `tw2002_aiclient/app.py` (`O` offer + App-armed auto-fire consumers); tip chain/explore/ship/
  trade modules under `tw2002_aiclient/`. **Archive-only (do-not-revive):**
  `archive/pre-rebirth-2026-07-23/.../twclient/autopilot.py` (`select()`, EV scorers,
  `EXPLORE_BASELINE_EV` auto-driver, `_priority_engine_focus_kind()`).
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
  [coaching-engine](/engine/coaching-engine.md),
  [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md) (confirm / strip consumers).
