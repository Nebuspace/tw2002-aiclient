---
type: System
title: Frontier Exploration Policy & Mechanism
description: When and how much to explore (appetite, turn budget, density-value interpretation) and the deterministic BFS/frontier planner that writes the world-model — a taught, human-armed behavior that STOPS on any unrecognized sector screen.
tags: [strategy, exploration, world-model, bfs, frontier, priority-input, hypothesis, prescriptive, stop-on-unknown]
timestamp: 2026-07-23T20:20:02Z
---

Exploration is how the trainer's map grows: pushing the known edge of the warp graph outward into
unmapped sectors, reading what is there, and writing every discovery into the persistent
[World Model](/engine/world-model.md) so it is never re-discovered from scratch in a later session.
This document is prescriptive spec, not an autonomous loop. It covers two separable things: the
**policy** — when to explore and how much, expressed as inputs the priority layer and the
rule-guards read — and the **mechanism** — the deterministic breadth-first frontier planner that
proposes the next hop and never blind-sends a keystroke.

The single most important thing to state up front, in the reborn framing, is what exploration is
**not**. It is not a "never-idle, keep-driving" appetite that lets the app wander the galaxy on its
own to fill dead air. The original v1 design treated exploration as a standing background drive that
always had *something* to do so a tick was never empty; that is retired. In the reborn client,
exploration is one of a small set of **taught, opt-in, human-armed behaviors**. It runs only when
the human has armed it, only within a turn budget, and — this is the invariant that overrides
everything else here — it re-validates the screen every single cycle and **STOPS, handing the human
the keyboard, on the first frame it does not recognize.** No exploration policy input, no
explore/exploit score, no computed frontier ever wins over that stop. The priority layer *ranks*
whether an armed explore behavior is worth suggesting or running relative to other taught behaviors;
it never picks a live action over an unrecognized sector screen.

# Schema

## The three explore intents (taught behaviors, TW-14)

Exploration ships as three distinct opt-in intents, each a taught behavior the human arms
separately, each respecting a turn budget, each halting on an unrecognized screen. They share the
one frontier planner underneath but differ in their goal:

- **Map-fill** — grow the known graph outward from the current sector. Picks the nearest unmapped
  frontier edge (with an ε-explore chance of sampling a farther one) and proposes a single valid
  adjacent hop toward it. This is the base intent the other two fall back to when their goal is not
  yet on the map.
- **Find-StarDock** — reach the StarDock. If a StarDock landmark is already recorded in the world
  model, pathfind the shortest known route to it and propose the next hop along that route. If no
  StarDock is known yet, fall back to Map-fill to hunt for it. When the frontier is also exhausted,
  a bounded recovery policy hops toward a known StarDock landmark, then toward the densest reachable
  sector, then **halts with attention** — it never returns a silent empty candidate list.
- **Find-Formations** — reach a catalogued special-formation candidate (a genesis-siting
  dead-end/bubble, surfaced by the topology pass — see [Special Formations](/strategy/special-formations.md)).
  Routes to the nearest catalogued candidate if one exists, else Map-fills to grow the graph.
  It **locates and routes only** — it never deploys Genesis; that is always a human-confirmed
  one-shot (see [Planet Colonization](/strategy/planet-colonization.md)).

The trainer panel cycles the active intent `off → mapfill → stardock → formations → off`. `off` is
the default: no explore behavior runs until the human arms one.

## The BFS / frontier planner mechanism (G1)

The planner is pure, deterministic, client-side planning. It reads the world-model sector graph and
returns the next warp target to *propose* — it emits no keystrokes itself. The mechanism:

1. Build the known graph: `sector_id → warps` for every sector currently on disk in this world.
2. **Frontier edges** — BFS outward from the current sector over *known* warps, collecting every
   edge whose destination is *not yet a key in the graph* (a warp we know leaves a known sector but
   whose target we have never recorded). Each frontier edge carries its BFS depth (hop-count from
   the current sector), and the frontier is sorted nearest-first.
3. **Pick an edge** with the ε-greedy knob (below): usually the nearest frontier edge (exploit the
   map's own shape), occasionally a random one (ε-explore, so distant regions stay reachable). A
   port-seed preference can bias exploit toward expanding a known-port's unmapped neighborhood for
   pair-hunting, while ε-explore still samples the whole frontier.
4. **Resolve to a valid single adjacent hop.** The chosen frontier edge's `frm` may be several known
   hops away from the current sector — the planner never hands back that edge's raw `to` sector as
   the next send. It resolves the edge into one valid hop that is genuinely adjacent to the current
   sector (the first step of the shortest known path toward the edge). SELECT is stateless and
   re-plans fresh every tick, so taking one valid hop at a time, re-evaluated each cycle, is both
   correct and sufficient — it never needs the whole path computed up front. This is the seam where
   "plan, don't blind-send" is enforced: a send is only ever a real, adjacent, game-legal warp.
5. **Record on arrival** (G1 write hook). Visiting the sector — via a density scan or an actual move
   — is what populates the world model: warps, port presence/class, visible threats, landmarks,
   formation membership, and an always-advancing `last_seen_ts`. The planner itself never writes;
   the parsers on the settled screen do. This keeps the store honest: a discovery is written only
   when the sector was actually observed.

Pathfinding for Find-StarDock / Find-Formations is shortest-path BFS on the same known warp graph.
Nothing here invents a warp that was never observed or guesses a price.

## Explore / exploit appetite — a priority INPUT, not a driver (G2)

The balance between exploring (scout unmapped sectors, cost turns against uncertain payoff) and
exploiting (replay proven [trade loops](/strategy/trade-loops.md), turn-efficient banked profit) is
a tunable ε-greedy knob, not a fixed split. In the reborn framing this knob is an **input to the
priority layer's ranking and to the frontier planner's edge choice** — it influences *which* taught
behavior gets suggested and *which* frontier edge Map-fill prefers. It is emphatically **not** a
live per-cycle action-picker that lets a computed exploration value beat out an unrecognized screen.

- **Mostly exploit.** The steady state is running known-good loops; only a budgeted fraction of
  turns goes to exploration.
- **Appetite RAISED when loops deplete (demand-driven).** A drying-up source port is the signal to
  hunt for fresh patterns — see [Port Economics](/strategy/port-economics.md). Depletion raises the
  *appetite to suggest exploring*; it never triggers autonomous rotation into a new loop. Depletion
  is a STOP-and-escalate / re-rank signal, not a license to auto-switch what the ship is doing.
- **Appetite LOWERED** when known loops are fresh and high-yield — no pressing reason to spend turns
  discovering more.
- A profitable new commodity pairing found while exploring is captured as a *candidate* loop (handed
  to the pattern-capture path — see [Trade Loops](/strategy/trade-loops.md)), never acted on as a
  live one-off. That is how the repertoire compounds across sessions without any autonomous trade.

## Density-scan value → content table (rule-guard + safety input)

Where a density scanner is available, scanning an adjacent sector *before* entering previews its
likely contents for a fraction of a turn's cost — a much cheaper way to map than visiting every
sector, and a **safety input**: a mine signature is a reason not to enter. This table feeds the
rule-guards (e.g. `density == 10` ⇒ mine ⇒ do-not-enter guard) and the frontier edge-preference; it
is never a fact the app acts on destructively without the human in the loop.

**Verification status:** UNVERIFIED / [hypothesis] against this server. The value→content mapping is
sourced from third-party TW2002-variant strategy-guide research, not from a direct in-game capture on
this server. Author portable *semantics* (a mine is a hazard-to-avoid; a port/StarDock is a nav
landmark); treat every numeric value below as a hypothesis to confirm before relying on it
operationally, and never hardcode these per-server.

| Scan value [hypothesis] | Hypothesized content | Guard / priority role |
|---|---|---|
| 1 | Beacon | landmark hint |
| 5 | Fighter | threat hint |
| 10 | Mine | **hazard — do-not-enter guard input** |
| 40 | Ship | threat / contact hint |
| 50 | Destroyed port | landmark hint |
| 100 | Port or StarDock | nav landmark (Find-StarDock seed) |
| 500 | Planet | landmark / colonization-siting hint |

## Runtime invariants (non-negotiable)

- **Human-armed before it runs.** No explore intent is live until the human arms it; `off` is the
  default. Arming a run is confirm-gated (see [Action-Safety Guards](/doctrine/action-safety-guards.md)).
- **Stop-on-unknown, every cycle.** The armed explore-macro re-validates the screen each tick and
  halts on the first unrecognized frame, surfacing a typed escalation reason to the human. The
  novelty-halt rail *is* stop-on-unknown at the safety layer (see
  [App Autopilot Model](/architecture/app-autopilot-model.md) and
  [Control & Escalation](/architecture/control-and-escalation.md)).
- **Priority ranks, never overrides.** The explore/exploit appetite and any frontier score order
  suggestions and armed behaviors — they can never let an exploration value win over a STOP.
- **Depletion ⇒ STOP-guard / re-rank, not autonomous rotation.** A depleting loop raises the
  appetite to *suggest* a hunt; it does not autonomously switch the ship into a new loop.
- **Plan, never blind-send.** Every proposed send is a real, adjacent, game-legal warp resolved
  against the known graph. The frontier planner never guesses a warp, price, or non-adjacent hop.
- **Locate / catalog / recommend — never claim.** Find-Formations routes to a candidate; deploying
  Genesis or colonizing is always a human-confirmed one-shot, never an autonomous competing candidate.

# Code divergence

The current code predates the reborn framing in three places. Recorded here per DOCS-WIN (docs are
the target; the code is noted as diverging, not silently conformed to):

- **`autopilot.py` — the "never-idle" explore baseline.** `EXPLORE_BASELINE_EV = 0.01` (autopilot.py
  ~line 269) exists specifically so a per-cycle EV SELECT always has *something* to do — the explore
  candidate is picked "whenever nothing else scores higher … so a tick always has SOMETHING to do,"
  with the rationale string `"keep exploring (…) — no idle (§11)"` (~line 742). This is exactly the
  retired "never-idle keep-driving" appetite. Reborn target: explore is a human-armed opt-in
  behavior, not a positive-EV floor that auto-fills idle ticks; `EXPLORE_BASELINE_EV` should not
  survive as an auto-driver justification.
- **`autopilot.py` — per-cycle EV action-picker.** The autopilot builds `Candidate(kind="explore",
  ev_per_turn=…)` rows and SELECTs the highest-EV candidate each tick. In the reborn model the
  priority layer *ranks/orders* taught behaviors and suggestions; it must not be a live per-cycle
  picker where a computed EV can win over an unrecognized screen. The stop-on-unknown gate must sit
  above SELECT, not compete inside it.
- **`trade_driver.py` — autonomous chain runner.** `run_chain()` drives a whole `ProfitChain` end-to-
  end synchronously in one call (routed from `AutopilotEngine._execute_chain()`); it carries
  interruptibility and fail-closed arming, but its shape is autonomous multi-step driving. Reborn
  target: a chain is a taught, human-armed repeating macro that re-validates and STOPS on unknown
  each step — the arm-confirm + per-step novelty-halt must bound it.
- **§22.4 / TW-23 capstone re-scope.** `DESIGN-v2.md` §22.4 still describes a "full-autopilot
  capstone" that "goes AUTOPILOT → seeks to DOUBLE starting credits autonomously," orchestrating
  explore + chain-find + holds + loop-trade. That autonomous-doubling end-state is counter-canon in
  the reborn vision and is re-scoped to human-armed, stop-on-unknown taught behaviors; the §15.4
  auto-explore behaviors it composes are the human-armed intents above, not an autonomous drive.

## Play explore flags — asymmetric by design

Play chrome exposes two explore automation booleans via
`tw2002_aiclient/cockpit/explore_flags.py` (wired through `adapters.explore_start_for_profile` /
daemon protocol):

| Flag | Play default | Meaning |
|---|---|---|
| `dock_new_ports` (gather) | **ON** (Max GO 2026-07-30 · WO-PLAY-EXPLORE-GATHER-DEFAULT-ON) | First-sight ports are entered for commodity ingest while Explore maps. Decoupled from `P)ort Trade·ON` (money gate for Trade Loop *execution* only — see [mode-line](/surfaces/mode-line-and-teach-controls.md)). |
| `fight_tolls` | **OFF** | Combat opt-in (`X`); calm `F` remains Find StarDock. |

CLI/daemon library defaults stay OFF for both — only the Play surface flipped gather ON.

**Do not tidy into symmetry.** `adapters.py` coerces `dock_new_ports` with `bool(...)` but
forwards `fight_tolls` **un-coerced** so a non-bool such as `"no"` reaches the daemon and trips
`invalid_fight_tolls` (coerced, `bool("no")` is `True` — an operator who declined combat would
have armed it). Hub-Accept'd 2026-07-29. `explore_flags.py` therefore holds real `bool`s and
never calls `bool()` on either flag (pins in `tests/test_play_explore_flags.py`). A future
"cleanup" that symmetrizes the two would be a defect, not a polish.

*(Honesty pass `AUDIT-CANON-DRAFT-EXPLORE-FLAGS-ASYMMETRY`, 2026-08-04.)*

# Citations

- design history §11 — explore/exploit appetite design (reborn-reframed: appetite = priority input,
  not idle-filling drive)
- design history §15.4 — auto-explore behaviors and world-model writes
- design history §16.2 — density-scan value table (flagged as hypothesis in source)
- design history §22.4 / TW-23 — full-autopilot capstone (re-scoped, DOCS-WIN)
- source module `explore.py` — TW-14 frontier/BFS planner (Map-fill / Find-StarDock / Find-Formations,
  recovery policy, adjacent-hop resolution)
- source module `world_model.py` — TW-06 persisted per-world sector store (G1 write target)
- source module `autopilot.py` — recorded EV-select / EXPLORE_BASELINE_EV divergence
- source module `trade_driver.py` — recorded autonomous chain-runner divergence
- tip Play flags — `tw2002_aiclient/cockpit/explore_flags.py` · `adapters.explore_start_for_profile`
  dock/fight asymmetry · [mode-line](/surfaces/mode-line-and-teach-controls.md) Explore vs `P` split
