---
type: Strategy
title: Planet Colonization & Production (human-gated)
description: Whether and where to colonize plus the turn-free production-income model — a recommendation the trainer surfaces to the operator; every Genesis deploy or colonize is a deliberate human-confirmed one-shot.
tags: [strategy, colonization, planets, production, human-gated, hypothesis, prescriptive]
timestamp: 2026-07-23T20:20:51Z
---

Planet colonization is the no-PvP builder's economic centerpiece: a colonized planet is a
turn-free, compounding income source — production accrues while the operator does nothing, unlike
port trading, which spends a game-turn on every cycle. This concept covers two questions the
trainer answers as **recommendations, never as autonomous acts**: *should* a candidate sector get a
planet, and *how* is a planet run once it exists. The load-bearing invariant, stated up front and
never softened below, is that committing a Genesis device or a colonize action is a real, costly,
hard-to-reverse in-game commitment — so the trainer **evaluates and recommends; the operator
confirms and fires**. Nothing here lets a computed production payoff execute a deploy on its own,
and nothing here lets a high colonization score outrank the app's stop-on-unknown reflex. The
priority layer that carries these recommendations *ranks and orders* what the operator should
consider; it is not a live per-cycle action-picker, and an attractive colonization candidate can
never win a tick over an unrecognized screen (see [Priority Engine](/engine/priority-engine.md) and
[Action-Safety Guards](/doctrine/action-safety-guards.md)).

# Schema

## The human-gate invariant (the spine)

Genesis and colonize are **irreversible, capital-heavy commitments**, so they are treated exactly
like every other value-bearing action in this project: the trainer may LOCATE, CATALOG, SCORE, and
RECOMMEND, but the actual commit is a deliberate operator-confirmed action, never an autonomous
competing candidate that a scoring loop can execute.

- The deploy is packaged, at most, as a **human-approved macro with `scope: one-shot`** — armed and
  fired only after the operator sees and confirms it, never a standing background loop and never a
  single keystroke to live money. Arming and launching go through the confirm-gate that
  [Action-Safety Guards](/doctrine/action-safety-guards.md) owns and that
  [Control & Escalation](/architecture/control-and-escalation.md) declares.
- A colonization recommendation is a **suggestion surfaced to the operator**, identical in status to
  a coaching tip: it appears in the ranked FOCUS list, it explains its rationale, and it waits. It
  does not arm itself, and it does not count as "coverage" of a taught screen.
- On any screen the app does not recognize while executing an approved deploy macro, the app STOPS
  at that first unrecognized frame and hands the operator the keyboard — the deploy macro is
  guarded and screen-matched every tick like any other rule, not run open-loop to completion.

This mirrors the formation detector's standing rule verbatim in spirit: the trainer LOCATES,
CATALOGS, RECOMMENDS — nothing more; deploying Genesis or claiming space is always an
operator-confirmed action (see [Special Formations](/strategy/special-formations.md)).

## Colonize-or-skip: candidate scoring

A candidate is a sector the trainer proposes as worth committing a planet to. Scoring weighs
**defensibility against production payoff**, over inputs the world model and the formation detector
already hold — the trainer scores what it has mapped, it does not go claim anything to find out.

- **Formation-siting inputs (defensibility).** The strongest siting signal is topology: a
  **dead-end** (a sector with a single warp exit) or a **bubble** (a sealed pocket reachable through
  a single entrance sector) is strongly preferred. The same shape that makes a sector easy to defend
  — few approach vectors, an intruder easy to notice — also makes it low-traffic and low-risk to
  colonize. These two topology kinds are exactly the set the formation detector flags as Genesis
  candidates. Colonization consumes them as **priority-ranking inputs**; note the operator-ruled
  separation: formations feeds *route-hazard guards* (one-way / warp-sink) on one axis and
  *colonization siting* (dead-end / bubble) on the other — the two docs stay separate and neither
  drives (see [Special Formations](/strategy/special-formations.md)).
- **Location value.** Proximity to a productive trade loop or a StarDock raises a candidate's value;
  proximity to hazards (toll sectors, hostile territory) lowers it. Distances come from the
  world-model warp graph's shortest-path primitive.
- **Production payoff.** The expected turn-free income the site could compound (the production
  engine below), weighed against the capital and defensibility cost of committing there.

The output is a ranked shortlist of candidate sectors with rationale — surfaced for the operator to
confirm, never a queued action. In the priority layer these colonization recommendations occupy
their own low-urgency rows (the colonization / Genesis-siting rows, historically rows 55 and 50 of
the priority table) — deliberately ranked *below* live-safety and active-trade concerns, because a
build-the-empire suggestion must never crowd out a hazard response or an escalation.

## The planet production engine (H5 — the compounding centerpiece)

Once a planet exists, it is the game's turn-free income lever. The production model, drawn from
design history and **entirely hypothesis-tagged** (see Verification status — no live capture and no
implementing module exists yet):

- **Turn-free compounding.** Production accrues daily without spending game-turns — the structural
  difference from port trading, which costs a turn per cycle. This is what makes planets the no-PvP
  builder's centerpiece.
- **Stored-cargo production bonus [hypothesis].** Commodity cargo left stored on the planet is
  hypothesized to raise its daily production rate by roughly one-tenth of the stored amount,
  permanently.
- **Compounding rate [hypothesis].** Untouched stored stock is hypothesized to compound at roughly
  **10% per day**.
- **Buy-production threshold [hypothesis].** Buying production outright with credits (no turns
  spent) is hypothesized to be worthwhile below a per-unit price around **9 credits**.
- **Spread-to-survive-plagues [hypothesis].** A random productivity loss — described in source
  material as affecting anywhere from roughly **1% to 99%** of a large productivity base — is an
  occasional risk. The mitigating strategy is to **spread capacity across multiple planets** (a
  documented ceiling of up to **100 planets per empire**) rather than concentrating everything in
  one mega-planet.

Reborn framing of the plague response: a productivity-loss / depletion event is a **STOP-guard, not
an autonomous rotation**. When concentration risk grows or a plague hits, the trainer *recommends*
rebalancing across planets and surfaces it to the operator — it never autonomously moves cargo,
relocates a planet, or reshuffles production to "recover" on its own. Depletion escalates; it does
not trigger a self-directed fix (this excises the AI-first "never idle, keep the empire optimally
balanced" appetite of the source material).

## Passive planet-value scouting (GF-growth estimator) [hypothesis]

A planet's **ground-force (GF) growth rate**, observed *passively over a short time window with no
attack*, is hypothesized to correlate with its stored credits — roughly **1 GF/min at a 100k GF
base**, scaling up toward **7 GF/min near 1M**. It offers a way to gauge a candidate site's or a
rival planet's value without engaging it. It is observational and non-hostile by construction
(watching a growth counter, not attacking), and it is unverified against the live game. It never
authorizes engaging another player's planet — combat and player-facing action remain the operator's
in-the-moment call under [Alignment & Conduct](/doctrine/alignment-and-conduct.md).

## The production-loop shape (planet as a trade leg)

The signature production loop from source material — buy a cheap commodity at a port, mass-transfer
it to the planet, then site the planet adjacent to a high-paying buyer port for a
one-turn-per-cycle sale — ties this strategy back to the pair-trade-loop shape once the planet
itself becomes one leg of the loop. When it does, the same reborn discipline applies: the loop is a
**taught, human-armed repeating macro** with a depletion STOP-guard, not an autonomous chain runner
that rotates on its own.

# Examples

A worked recommendation (illustrative — numbers are hypothesis-tagged, never planning constants):

```
CANDIDATE SHORTLIST (recommendation — awaiting operator confirm)
  1. Sector 4931  [dead-end]   siting: single warp exit · 2 hops from Class-BBS loop
                                payoff: hypothesized turn-free compounding site
                                → RECOMMEND colonize (one-shot, human-confirmed)
  2. Sector 4712  [bubble]     siting: sealed 3-sector pocket, one entrance · defensible
                                payoff: farther from a buyer port (−location value)
                                → RECOMMEND (secondary)

  Genesis / colonize is a deliberate operator-confirmed action.
  Nothing here is armed. Press to review; confirm to fire the one-shot deploy macro.
```

The trainer never advances past this shortlist on its own. The operator picks a candidate, reviews
the one-shot deploy macro, and confirms it; only then does the app replay it — screen-matched and
STOP-guarded every tick.

# Verification status

- **VERIFIED (grounded in code):** the formation-siting inputs — dead-end (single outbound warp) and
  bubble (single-entrance sealed pocket) detection, and their designation as the Genesis-candidate
  set — are implemented as a pure topology pass in `formations.py` (`GENESIS_TYPES = {dead-end,
  bubble}`, `detect_formations`, `catalog_world`), reading the world-model warp graph and emitting
  operator-facing hints only. The LOCATE / CATALOG / RECOMMEND-only posture is enforced structurally:
  that module never deploys or claims.
- **HYPOTHESIS (design-history only — no live capture, no implementing module):** every production
  number — the ~1/10-of-stored-cargo daily production bonus, the ~10%/day compounding rate, the
  ~9-credit buy-production threshold, the ~1%–99% plague loss band, the ~100-planet-per-empire cap,
  and the GF-growth-vs-stored-credits estimator (~1 GF/min at 100k → ~7 GF/min near 1M). All must be
  confirmed against locally-observed production deltas on the live game before being used as planning
  constants, and each carries its own inline caveat wherever consumed. Per project discipline, no
  per-server stat value is hardcoded in canon — these are portable *semantics* (a stored-cargo bonus
  exists, production compounds, plague is a spread-to-survive risk); the live numbers are
  introspected, not asserted (see [Game-Data Store](/engine/game-data-store.md)).

# Code divergence

- **No planet-production engine exists in code.** The entire H5 production model (stored-cargo bonus,
  compounding, buy-threshold, plague spread, GF-growth scouting) is authored here as target semantics
  from design history; there is no module that reads or models planet production, and no live capture
  of a planet screen. This is a build gap, not a behavioral defect — recorded so the docs win and the
  gap is not silently conformed away.
- **Formations siting inputs are computed and membership is written** (#326): dead-end/bubble
  genesis candidates flow through the shared detector / panel / `recommend_genesis` alias. There is
  still **no autonomous Genesis deploy** and no new product surface that auto-invokes
  `recommend_genesis` beyond the catalogue — RECOMMEND-only doctrine holds. Membership writeback and
  route-hazard guards are documented in [Special Formations](/strategy/special-formations.md)
  § Code reality (#326–#331). The confirm-to-send choke-point for any future App Genesis send is
  documented under [Action-Safety Guards](/doctrine/action-safety-guards.md)
  § Genesis confirm-to-send choke-point (`genesis_confirm.py`, Option A shipped / Option B HELD).
- **The priority layer's inherited "never-idle" appetite is counter-canon here.** The AI-first
  originals carried a per-cycle EV-selection habit (the autopilot's `EXPLORE_BASELINE_EV` "never
  idle" floor and `trade_driver`'s autonomous chain runner) in which a computed payoff could pick the
  next live action. In the reborn framing that is explicitly excised for colonization: a production
  EV never fires a deploy, and a colonization score never outranks stop-on-unknown. The priority
  engine ranks these recommendations; it does not execute them. Recorded as a framing divergence the
  reborn priority-engine and app-autopilot-model docs also carry.

# Citations

- design history §16.2 — planet production engine: storage bonus, compounding rate, credit-buy
  threshold, plague-loss band, per-empire planet cap.
- design history §16.4 — the ground-force-growth observational planet-value estimator (noted
  unverified in source).
- design history §12 / §15.5 — the special-formation detector and Genesis appetite: locate/catalog
  candidates, human-confirmed commit.
- `formations.py` — the dead-end / bubble Genesis-candidate topology pass, membership writeback,
  and `recommend_genesis` alias (no autonomous deploy).
- `world_model.py` — the warp-graph and landmark substrate the siting scorer reads (planets surface
  only as an `own_planet` landmark and a density-scan `500=planet` presence hint; no production
  fields).
- [Special Formations](/strategy/special-formations.md) — siting inputs (dead-end / bubble),
  kept separate per operator ruling.
- [Control & Escalation](/architecture/control-and-escalation.md) — the human-gated deploy /
  confirm-gate mechanics.
- [Action-Safety Guards](/doctrine/action-safety-guards.md) — the byte-level confirm gate and the
  irreversible-commit rule.
- [World Model](/engine/world-model.md) — the read-only siting substrate.
- [Priority Engine](/engine/priority-engine.md) — where colonization recommendations rank (the
  colonization / Genesis-siting rows), ordering not execution.
- [Alignment & Conduct](/doctrine/alignment-and-conduct.md) — the never-initiate boundary around
  rival planets and player-facing action.
