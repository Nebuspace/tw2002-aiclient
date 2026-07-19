---
type: Strategy
title: Frontier Exploration
description: Systematic frontier/BFS exploration of the warp graph, balanced against exploitation of known-profitable loops, that writes every discovery into the persistent world-model.
tags: [strategy, exploration, world-model, hypothesis]
timestamp: 2026-07-19T16:11:33Z
---

Exploration is a first-class drive, not only a fallback when idle: seeking out new trading
patterns and territory grows the strategy repertoire over time instead of only replaying what was
already demonstrated.

# What it is
- A frontier (BFS-style) traversal of the sector warp-graph: from the current position, push
  outward into unvisited/unmapped sectors, extending the known map's edge outward rather than
  wandering randomly.
- Reads density-scan results, where available, to preview adjacent-sector contents before spending
  a turn to enter — a much cheaper way to map than visiting every sector directly. See
  [TW2002 Ships and Equipment](/reference/tw2002-ships-and-equipment.md) for what the density
  scanner is and its acquisition tradeoff.

# When it applies
- As a standing, budgeted background appetite rather than only a fallback: exploration should
  consume some share of turns even when known loops are working.
- Raised (more turns allocated to exploration) when a currently-worked loop's stock is visibly
  depleting (see [Port Economics](/strategies/port-economics.md)) — a drying-up source port is the
  demand signal that should trigger a fresh hunt, not merely random chance.
- Lowered when known loops are fresh/high-yield and there is no pressing reason to spend turns
  discovering more.

# Tradeoffs — explore vs exploit
- **Exploit** (run proven loops from the loop library) is the reliable, turn-efficient way to bank
  profit from what is already known.
- **Explore** (scout unmapped sectors, test new commodity/port pairs) costs turns against uncertain
  payoff, but is the only way the repertoire of known-good loops grows.
- The balance is a tunable explore/exploit knob (an epsilon-style mostly-exploit,
  occasionally-explore ratio) rather than a fixed split, and should react to the depletion signal
  above rather than stay static.
- A profitable new pattern discovered while exploring should be captured as a candidate loop rather
  than treated as a one-off — see [Pair Trade Loops](/strategies/pair-trade-loops.md) — this is how
  the repertoire compounds across sessions.

# Steps
1. From the current sector, identify the nearest unmapped frontier (adjacent sectors not yet in
   the world-model).
2. Where a density scanner is available, scan before entering to pre-filter — read the returned
   signature to infer likely contents (see below) and prioritize sectors worth a full visit.
3. Enter and record: warps, port presence/class, any visible threat, and any landmark — write every
   discovery into the persistent [World Model](/architecture/world-model.md) so it is never
   re-discovered from scratch in a later session.
4. If a profitable new commodity pairing or port is found, hand it to the pattern-capture path so
   it can graduate into the loop library.
5. Re-evaluate the explore/exploit ratio periodically, and especially whenever a worked loop's
   depletion signal fires.

# Density-scan signature reference

**Verification status:** UNVERIFIED against the live game. The value-to-content mapping below is
sourced from third-party TW2002-variant strategy-guide research, not from a direct in-game capture
on this server. Treat every value below as a hypothesis to confirm before relying on it
operationally.

| Scan value | Hypothesized content |
|---|---|
| 1 | Beacon |
| 5 | Fighter |
| 10 | Mine |
| 40 | Ship |
| 50 | Destroyed port |
| 100 | Port or StarDock |
| 500 | Planet |

# Citations
[1] design history §11 — explore/exploit appetite design
[2] design history §16.2 — density-scan value table, flagged as a hypothesis in source
[3] design history §15.4 — auto-explore behaviors and world-model writes
