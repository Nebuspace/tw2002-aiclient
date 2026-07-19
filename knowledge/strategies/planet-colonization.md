---
type: Strategy
title: Planet Colonization
description: Decision framework for whether and where to colonize a planet, weighing location/defensibility against expected production payoff.
tags: [strategy, colonization, planets, hypothesis]
timestamp: 2026-07-19T16:11:33Z
---

# What it is
The decision of whether a candidate sector is worth committing a planet (via Genesis or
colonization) to, and how to run it once colonized. Planets are the compounding, turn-free income
lever in a no-PvP builder-style game: once colonized, production accrues without spending turns,
unlike port trading.

# When it applies
- After exploration (see [Frontier Exploration](/strategies/exploration.md)) and
  formation-detection (see [Special Formations](/doctrine/special-formations.md)) have identified a
  candidate sector.
- Most attractive candidates are dead-ends (single warp exit) or bubbles (sealed pockets with one
  way in) — the same topology that makes a sector easy to defend also makes it a low-traffic,
  low-risk site to colonize.

# Colonize-or-skip decision inputs
- **Location value:** proximity to a productive trade loop or a StarDock, versus proximity to
  hazards (toll sectors, hostile territory).
- **Defensibility:** a dead-end or bubble (see
  [Special Formations](/doctrine/special-formations.md)) is strongly preferred — fewer approach
  vectors to defend, easier to notice an intruder.
- **Production expectations (hypothesis):** commodity cargo left stored on the planet is
  hypothesized to raise its daily production rate by roughly one-tenth of the stored amount,
  permanently; untouched stock is hypothesized to compound at roughly 10% per day; buying
  production outright with credits (no turns spent) is hypothesized to be worthwhile below a
  per-unit price around 9 credits. All three are unverified against the live game and must be
  confirmed before being used as planning constants.
- **Plague/loss risk (hypothesis):** a random productivity loss affecting anywhere from roughly 1%
  to 99% of a large productivity base is described in source material as an occasional risk — the
  mitigating strategy is to spread capacity across multiple planets (a documented ceiling of up to
  100 per empire) rather than concentrating everything in one mega-planet.
- **Passive planet-value scouting (hypothesis):** a planet's ground-force growth rate, observed
  passively (no attack) over a short time window, is hypothesized to correlate with its stored
  credits (roughly 1 GF/min at a 100k GF base, scaling up to roughly 7 GF/min near 1M) — a way to
  gauge a candidate or rival planet's value without engaging it. Unverified against the live game.

# Tradeoffs
- A well-placed, well-defended planet is a compounding, turn-free income source — a fundamentally
  different economic shape than port trading, which always costs turns per cycle.
- The signature production loop described in source material — buy a cheap commodity at a port,
  mass-transfer it to the planet, then relocate the planet adjacent to a high-paying buyer port for
  a one-turn-per-cycle sale — ties this strategy back to the pair-trade-loop shape (see
  [Pair Trade Loops](/strategies/pair-trade-loops.md)) once the planet itself becomes one leg of
  the loop.
- Concentration risk: per the plague hypothesis above, spreading production across several smaller
  planets is safer than one large one, at the cost of more sites to manage/defend.
- Actually committing a Genesis device or colonization action is a real, costly, hard-to-reverse
  in-game commitment — this strategy covers evaluating and recommending a candidate, not
  autonomously acting on one.

# Steps
1. From the world-model / formation catalog, shortlist dead-end and bubble sectors within
   reasonable reach of a productive trade lane.
2. Score each candidate on location value and defensibility.
3. Recommend the best candidate(s) for colonization; the actual commit (Genesis / colonize) is a
   deliberate, human-confirmed action, not an autonomous one.
4. Once colonized, feed cargo/credits toward production per the hypothesis above, verifying the
   effect against locally-observed production deltas rather than assuming the source numbers hold.
5. Monitor for plague-style productivity loss and rebalance across planets if concentration risk
   grows.

# Citations
[1] design history §16.2 — planet production engine: storage bonus, compounding rate, credit-buy
    threshold, plague risk, planet cap
[2] design history §12 / §15.5 — special-formation detector and genesis appetite: locate/catalog
    candidates, human-confirmed commit
[3] design history §16.4 — ground-force-growth observational planet-value estimator, noted
    unverified in source
