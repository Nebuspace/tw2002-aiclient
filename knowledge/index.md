---
okf_version: "0.1"
---

# tw2002-aiclient — Canonical Knowledge Bundle

The canonical, curated knowledge library for the AI-native TradeWars 2002 client. Concepts here
are prescriptive: they are the truth about their subjects, and code conforms to them. Start with
the architecture vision, then drill into strategies, reference, and doctrine as needed.

# Architecture

* [Trainer Vision](architecture/trainer-vision.md) - The AI pilots the game while the client learns profitable loops from demonstration, graduating toward autonomous flight as its learned repertoire grows.
* [Session Engine](architecture/session-engine.md) - The built two-process engine (a session daemon plus a one-shot CLI) that gives an LLM a clean, settled screen back in one round trip while a control-lock mode machine governs who may drive it.
* [World Model](architecture/world-model.md) - A per-world, per-sector knowledge store of warps, ports, threats, and landmarks that every exploration, coaching, and routing behavior reads from.
* [Autonomy Loop](architecture/autonomy-loop.md) - Every keystroke is attributed to who or what generated it, feeding a graduation gauge and a retro tool that mines a session for AI decisions worth codifying.

# Strategies

* [Pair Trade Loops](strategies/pair-trade-loops.md) - Cycle between two (or more) complementary ports that buy and sell opposite commodities, scoring profitability by credits-per-turn rather than credits-per-trip.
* [Frontier Exploration](strategies/exploration.md) - Systematic frontier/BFS exploration of the warp graph, balanced against exploitation of known-profitable loops, that writes every discovery into the persistent world-model.
* [Port Economics](strategies/port-economics.md) - Port classification, price-spread behavior, stock/regrowth dynamics, and floor-price concepts that determine how sustainable and how profitable a given trade loop is.
* [Toll and Defense Math](strategies/toll-and-defense-math.md) - Decision framework for handling toll-sector NPC fighters and mine encounters — when to fight through, pay, or reroute, and how much defense is enough.
* [Planet Colonization](strategies/planet-colonization.md) - Decision framework for whether and where to colonize a planet, weighing location/defensibility against expected production payoff.

# Reference

* [TW2002 Ships and Equipment](reference/tw2002-ships-and-equipment.md) - Portable conceptual knowledge of what ships and key equipment (density scanners, TransWarp) are and mean, with per-server stat values introspected into a live game-data store rather than authored here.

# Doctrine

* [Paladin Ethos](doctrine/paladin-ethos.md) - The behavioral constitution for autonomous and trainer-driven play — protective-by-default, never-initiate-PvP, human-gated defense, and independent-play integrity.
* [Special Formations](doctrine/special-formations.md) - How the trainer identifies warp-graph topology anomalies (dead-ends, bubbles, one-way warps, warp-sinks) and the strict operator-confirmation boundary on acting upon them.

# Conventions

* Unverified game-mechanics numbers are hypothesis-tagged (`tags: [..., hypothesis]`) and carry an
  explicit **Verification status** line — they are configurable coaching parameters until verified
  against the live game, never hardcoded facts.
* Per-server game DATA (ship stats, item catalogs) is introspected at runtime into the game-data
  store; this bundle authors only portable semantics and schemas.
* Citations reference the project's internal design history by section (plain text) — the design
  journals themselves are private working documents, not part of this bundle.
