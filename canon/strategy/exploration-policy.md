---
type: System
title: Frontier Exploration Policy & Mechanism
description: When and how much to explore (appetite — depletion and affordability triggers sharing explore_appetite_raised, turn budget, density-value interpretation), the deterministic BFS/frontier planner (Map-fill family), and the Chain-hunt sibling-exhaust intent that grows the map for maximal trade-loop chain length — taught, human-armed behaviors that STOP on any unrecognized sector screen.
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

## The four explore intents (taught behaviors, TW-14)

Exploration ships as four distinct opt-in intents, each a taught behavior the human arms
separately, each respecting a turn budget, each halting on an unrecognized screen. Map-fill,
Find-StarDock, and Find-Formations share the one BFS/frontier planner underneath (G1) but differ
in their goal. **Chain-hunt** is a fourth intent with its own sibling-exhaust planner (below) —
it does **not** reuse Map-fill's global nearest-first frontier pick.

- **Map-fill** — grow the known graph outward from the current sector. Picks the nearest unmapped
  frontier edge (with an ε-explore chance of sampling a farther one) and proposes a single valid
  adjacent hop toward it. This is the base intent Find-StarDock / Find-Formations fall back to when
  their goal is not yet on the map. It is **not** an adequate chain-hunting strategy: it does not
  exhaust a port sector's own unmapped siblings before the frontier advances past them.
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
- **Chain-hunt** — grow the known graph in a **chain-length-maximizing** shape: at a sector with a
  confirmed port, exhaust that sector's unmapped warp-neighbors (visit → free flyby read → return)
  before advancing the frontier past any of them; when a neighbor itself has a port, recurse; on a
  dead end, backtrack to the nearest ancestor port that still has unexhausted neighbors. Explicit
  tradeoff vs Map-fill: ~**2× hop count** (there-and-back per sibling instead of one-way advance)
  for guaranteed maximal chain-length discovery in the covered area. See **Chain-hunt mechanism**
  below. Counterpart relationship to `chains.py` cycle-search is noted in
  [Trade Loops](/strategy/trade-loops.md) — Chain-hunt does not call into or replace that finder.

Arming surfaces (tip-true): Play's Explore offer stays **2-wide** —
`map_fill` / `find_stardock` via `ARMABLE_INTENTS` and the find-StarDock toggle (`#247` /
WO-RETIRE-CYCLE-EXPLORE-MODE). Play's confirm-arm site **refuse-gates** at runtime: if the armed
intent is not in that 2-wide tuple, `app.py` raises `ValueError` (PR `#677` —
`WO-CLEANUP-ARMABLE-INTENTS-ENFORCEMENT-TIPCHECK`); the set is not documentation-only. It is **not** a rotating
`off → mapfill → stardock → formations → chainhunt → off` panel cycle. `find_formations` and
`chain_hunt` are **CLI/daemon-armable and LIVE** (`tw explore start --intent …`; Chain-hunt
planner + wiring shipped in PR `#640` / `#641`) — they are deliberately **not** on Play's E
cycle. `off` remains the default: no explore behavior runs until the human arms one.

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

## Chain-hunt mechanism (sibling-exhaust + ancestor-port backtrack)

Chain-hunt is a **separate taught intent** from Map-fill. It still proposes only valid adjacent
hops (plan-never-blind-send), still re-validates the screen every cycle (stop-on-unknown), and
still writes discoveries only through the normal observe/parse path into the
[World Model](/engine/world-model.md). What changes is **which** frontier work it chooses next.

### Motivation (why Map-fill is not enough)

Map-fill's G1 pick is global nearest-first over the whole frontier. Concrete failure for chain
hunting (operator walkthrough, 2026-08-09): sector **5** has a port and warps to unmapped **6**,
**7**, **8**. Map-fill may visit one neighbor and then let the frontier push onward from that
neighbor without ever returning to exhaust 5's remaining siblings — so a port chain that would
have been visible by sweeping 5's closed neighbor set is left incomplete. Recovery after a dead
end falls through to generic exhausted-frontier heuristics (`plan_exhausted_recovery` /
densest-reachable), which are map-fill shaped and **not** chain-aware. Chain-hunt exists to close
that gap as net-new strategy canon (G1's description of Map-fill remains accurate to code).

### Sibling-exhaust rule

1. **Anchor on a confirmed-port sector.** While Chain-hunt is armed and the current (or resumed)
   focus sector has a confirmed port in the world model, treat that sector's **unmapped
   warp-neighbors** as a closed work set to exhaust **before** treating any farther frontier as
   the next primary expansion.
2. **Visit one unmapped sibling at a time.** Propose the adjacent hop from the port sector to one
   unmapped neighbor; on arrival, read the free flyby / sector screen (port presence/class, warps,
   threats) into the world model — **no dock required** for the no-port / port-presence decision.
3. **Return to the port sector.** After the flyby read, the next proposed hop is back to the
   anchoring port sector (or along the known shortest path back to it if an intervening move was
   required). That closes the sibling's visit as a there-and-back, not a one-way Map-fill advance.
4. **Classify the sibling, then continue the set.**
   - **No port** — that branch is closed. Cheap cost: one round-trip. Resume exhausting remaining
     unmapped siblings of the same anchor.
   - **Has a port** — that neighbor becomes the **new chain frontier / new anchor**. Recurse the
     same exhaust-then-advance rule from there (its own unmapped siblings become the next closed
     set). The previous anchor remains on an ancestor stack for backtrack.
5. **Advance only after the closed set is empty.** Only when the current anchor has no remaining
   unmapped warp-neighbors does Chain-hunt advance the primary focus to the next port frontier
   produced by step 4 (or backtrack per below).

### Backtrack on dead end

When the current focus sector is **fully exhausted** (all known warp-neighbors mapped) **and** it
has **no port** (or is otherwise not a viable chain anchor), Chain-hunt **does not** use Map-fill's
generic exhausted-frontier recovery. It **backtracks to the nearest ancestor port** on the
Chain-hunt stack that still has unexhausted unmapped neighbors, and resumes sibling-exhaust there.
If no such ancestor remains and the turn budget / depth cap is not yet spent, the intent may fall
back to Map-fill only as an explicit last resort to keep the graph growing — never silently
substitute densest-reachable recovery for chain-aware backtrack while an ancestor port still has
open siblings.

### Explicit hop-cost tradeoff (~2×)

State this plainly — it is a real turn-budget cost, not an implementation footnote:

- Map-fill pays roughly **1×** hop cost per newly mapped neighbor (one-way advance along the
  chosen frontier).
- Chain-hunt pays roughly **2×** hop cost per sibling in the closed set (there **and** back to the
  port anchor) so every sibling of a confirmed port is observed before the frontier is allowed to
  abandon that port's neighborhood.
- The exchange is **guaranteed maximal chain-length discovery in the covered area** (every
  port-adjacent unmapped edge considered under the exhaust rule) versus Map-fill's cheaper but
  incomplete neighborhood sweep.

Numeric **built-in defaults** for **sibling-exhaust depth limit** and **per-run
turn-budget cap** are **not** fixed here — they remain Pending in
[`canon/DECISIONS.md`](/DECISIONS.md) (`PENDING-CHAIN-HUNT-SIBLING-EXHAUST-DEPTH-TURN-CAP`).
Tip arming already requires explicit caller-supplied `--exhaust-depth` / `--turn-budget`
(fail-closed; no invented defaults — PR `#640` / `#641`). The Pending ruling is only whether
optional built-in defaults may later be shipped when those flags are omitted — not a gate on
building or arming Chain-hunt itself.

### Runtime invariants (same as every explore intent)

Chain-hunt remains subject to every standing explore invariant: human-armed opt-in, stop-on-unknown
every cycle, plan-never-blind-send (adjacent legal warps only), locate/catalog/recommend-never-claim,
and priority-ranks-never-overrides-STOP. It grows the map; it does not execute trade loops, dock for
commerce, or call into `chains.py`.

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
  Tip writes this as `explore_appetite_raised` from
  `chain_depletion.depletion_signals()` (`chain_depletion.py` ~148–165) onto chain status when
  `nearing_depletion` is true — **FOCUS consumer LIVE** (`focus_status.recommend_focus_candidates`
  raises explore `overlay_weight` via `WEIGHT_EXPLORE_APPETITE` when the flag is true;
  WO-BUILD-EXPLORE-APPETITE-FOCUS-CONSUMER). Do not invent a parallel appetite bit.
  Affordability as a second OR-cause of the same flag remains Pending
  (`PENDING-AFFORDABILITY-EXPLORE-WEIGHT-DEFINITION`).
- **Appetite RAISED when credits cross a known upgrade/fighter cost (affordability-driven).** Once
  current credits clear a known cargo-hold upgrade quote and/or fighter unit cost (the same math
  surface as `priority_engine.afford_fighters`, which today only feeds GOALS labels), grinding an
  inefficient known loop is no longer the only rational move — exploring for StarDock / fresh loops
  becomes a louder FOCUS suggestion so the operator can act on what exploring finds. **Same signal,
  second OR-cause:** affordability MUST set / extend the existing `explore_appetite_raised` flag
  (shared consumer with depletion), never a second competing boolean. Exact threshold definition
  (raw credits ≥ cost vs safety margin above trade float; whether hold-upgrade and fighter costs
  nudge with different strength) is Pending —
  `PENDING-AFFORDABILITY-EXPLORE-WEIGHT-DEFINITION` in [DECISIONS](/DECISIONS.md). Ranking input
  only — never an autonomous FOCUS rotation or live drive.
- **Appetite LOWERED** when known loops are fresh and high-yield **and** credits have not crossed a
  known affordability threshold — no pressing reason to spend turns discovering more.
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
- **Depletion or affordability ⇒ STOP-guard / re-rank, not autonomous rotation.** A depleting
  loop **or** credits clearing a known hold-upgrade/fighter cost raises the appetite to *suggest* a
  hunt (via the shared `explore_appetite_raised` signal); it does not autonomously switch the ship
  into a new loop or change live drive.
- **Plan, never blind-send.** Every proposed send is a real, adjacent, game-legal warp resolved
  against the known graph. The frontier planner never guesses a warp, price, or non-adjacent hop.
- **Locate / catalog / recommend — never claim.** Find-Formations routes to a candidate; deploying
  Genesis or colonizing is always a human-confirmed one-shot, never an autonomous competing candidate.

# Code divergence

The tip/archive history predates the reborn framing in places. Recorded here per DOCS-WIN (docs are
the target). **Archive-only** shapes are do-not-revive — not open tip defects to "fix":

- **Schema arming cycle — tip-true (closed 2026-08-10).** Older Schema prose claimed a trainer-panel
  cycle `off → mapfill → stardock → formations → chainhunt → off` and called Panel/CLI wiring for
  `chainhunt` a "follow-on build." Tip is otherwise: Play E stays **2-wide** (`ARMABLE_INTENTS` =
  `map_fill`, `find_stardock`); `find_formations` / `chain_hunt` are CLI/daemon-armable and **already
  shipped** (`plan_chain_hunt` / `INTENT_CHAIN_HUNT` / CLI — PR `#640` / `#641`). Do not re-open as
  "chain_hunt unbuilt" or as a 4-/5-step panel cycle.
- **Chain-hunt numeric defaults prose — tip-true (closed 2026-08-10).** Older mechanism prose said
  depth/turn caps "must be ruled before the follow-on build WO hard-codes them," which re-reads as
  "Chain-hunt is still unbuilt." Tip already arms with **required** caller flags and no defaults
  (`#640`/`#641`); DECISIONS Pending is **defaults-only** (`#668`). Do not re-open as a build gate.
- **Archived `autopilot.py` "never-idle" explore baseline — do-not-revive.** Pre-rebirth
  `EXPLORE_BASELINE_EV = 0.01` existed so a per-cycle EV SELECT always had *something* to do
  (`"keep exploring (…) — no idle (§11)"`). That module is **gone from tip**. Reborn: explore is a
  human-armed opt-in behavior; tip may keep a FOCUS *suggestion* floor only
  ([app-autopilot-model](/architecture/app-autopilot-model.md)).
- **Archived `autopilot.py` per-cycle EV action-picker — do-not-revive.** Archive built
  `Candidate(kind="explore", …)` rows and SELECTed the highest-EV candidate each tick. Tip priority
  *ranks/orders* taught behaviors and suggestions; it must not revive a live per-cycle picker where
  a computed EV can win over an unrecognized screen. Stop-on-unknown sits above SELECT.
- **`trade_driver.py` — autonomous chain runner, RESOLVED, closed 2026-08-09.** `run_chain()` drives
  a whole `ProfitChain` end-to-end, but per-step re-validation and human-armed gating are proven, not
  open: `_navigate` (~L764-841) re-validates `classify_screen` before every warp send, and every send
  funnels through `_confirmed_send()` (~L359-403), which fails closed on `ctx.armed()`/
  `should_abort()`. See [Port Economics](/strategy/port-economics.md)'s matching Code divergence
  entry and [toll-and-defense](/strategy/toll-and-defense.md) Option C fact-find (re-verified against
  tip `7c97b2a`) for the citation trail — do not re-litigate this as an open gap in either doc.
- **§22.4 / TW-23 capstone re-scope.** Design history §22.4 still describes a "full-autopilot
  capstone" that "goes AUTOPILOT → seeks to DOUBLE starting credits autonomously." That
  autonomous-doubling end-state is counter-canon and re-scoped to human-armed, stop-on-unknown taught
  behaviors; the §15.4 auto-explore behaviors it composes are human-armed intents, not idle-fill drive.

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

## Pre-uncharted defensive posture (sibling gate)

Before map-fill commits to an **uncharted** warp, tip may consult the pure
[Explore Defensive Posture](/strategy/explore-defensive-posture.md) decision
(`session/explore_defensive_posture.py`): if fighters are under a judgment floor and a known
StarDock dealer is in budget, explore seeks the dealer then halts for a human-gated purchase —
it never auto-buys. Unknown / unreachable / unaffordable inputs fail closed to ordinary explore.
Policy numbers there are judgment defaults, not Max-ratified combat math (do not conflate with the
stripped toll-defense floors in [toll-and-defense](/strategy/toll-and-defense.md)).

## Session continuity on `ExploreRunner.start()` (tip contract)

`tw explore start` does **not** open a second telnet connection and does **not**
construct a new `Session`. The daemon owns one `ExploreRunner` wired at startup
(`session/daemon.py` → `server.sector_explore = ExploreRunner(session, …,
guardian=guardian)`). Protocol `_dispatch_explore_start` (`session/protocol.py`)
resolves that runner and calls `runner.start(...)`; the driver thread
(`ExploreRunner._run`, name `tw-sector-explore`) shares the **same** `Session`
object and `control_lock` as every other auto-loop / CLI send path.

**Gate vocabulary.** Each cycle re-renders and runs `_gate_screen`
(`session/sector_explore.py`): `main_command` (movement) passes; never-auto
classes halt as `never_auto_action:<klass>`; other named classes halt as
`halt_not_drivable:<klass>`; genuine classifier unknowns halt as bare
`unrecognized_screen`. Halt behaviour is stop-on-unknown — the reason string
must not lie about whether `classify` named the screen.

**Guardian reconnect overlap (why `game_select` was a false halt).** On a
multi-game BBS, SessionGuardian D9 reconnect+login-replay transiently paints
`game_select` while replaying into the same session. Before PR #554 /
`WO-DIAGNOSE-EXPLORE-HALT-GAME-SELECT-LIVE-SESSION`, explore's gate treated that
transient as a genuine `halt_not_drivable:game_select` even though a later
`tw status` already showed `main_command` again. Tip now:

1. Passes `guardian=` into `ExploreRunner` so the loop can observe
   `guardian.reconnecting`.
2. When a halt fires **while** `reconnecting` is true, waits a bounded window
   (`RECONNECT_WAIT_TIMEOUT_S` / `RECONNECT_WAIT_POLL_S`) for the burst to
   clear, then re-renders and re-gates from the top of the loop — never an
   unbounded retry if the burst never clears.
3. Uses settle profiles with `retry_unstable_idle=True` on explore waits so a
   short unstable idle during recovery does not fail-fast the settle.

This is **session continuity**, not a second connection: two drivers
(guardian replay + explore) briefly share one session; explore must not
mistake the replay's own screens for an unrecoverable explore halt.

**Live evidence (post-fix).** Sacrificial `scout_academy` credit-doubling
live-prove (2026-08-09) re-ran `tw explore start … --dock-new-ports` to
`outcome=completed` after #554 — see coord STATUS for that prove and the
research note update in
[autopilot-live-drive-findings-2026-08-08](/research/autopilot-live-drive-findings-2026-08-08.md)
Axis 5.

# Citations

- design history §11 — explore/exploit appetite design (reborn-reframed: appetite = priority input,
  not idle-filling drive)
- design history §15.4 — auto-explore behaviors and world-model writes
- design history §16.2 — density-scan value table (flagged as hypothesis in source)
- design history §22.4 / TW-23 — full-autopilot capstone (re-scoped, DOCS-WIN)
- source module `explore.py` — TW-14 frontier/BFS planner (Map-fill / Find-StarDock / Find-Formations,
  recovery policy, adjacent-hop resolution); Chain-hunt planner is **in tip** after PR #640 / merge
  `39a8634c` (`INTENT_CHAIN_HUNT` / `plan_chain_hunt` in `explore.py` — do not treat Map-fill pick as Chain-hunt)
- source module `world_model.py` — TW-06 persisted per-world sector store (G1 write target)
- source module `autopilot.py` — **archive-only** EV-select / `EXPLORE_BASELINE_EV` (do-not-revive)
- source module `trade_driver.py` — RESOLVED autonomous chain-runner (per-step classify + armed send; see Code divergence)
- tip Play flags — `tw2002_aiclient/cockpit/explore_flags.py` · `adapters.explore_start_for_profile`
  dock/fight asymmetry · [mode-line](/surfaces/mode-line-and-teach-controls.md) Explore vs `P` split
- tip `session/sector_explore.py` — ExploreRunner same-session start + guardian reconnect wait (`RECONNECT_WAIT_*`) · `session/daemon.py` ExploreRunner wiring · `session/protocol.py` `_dispatch_explore_start`
