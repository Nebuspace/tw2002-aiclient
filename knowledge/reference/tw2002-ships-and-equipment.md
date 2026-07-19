---
type: Reference
title: TW2002 Ships and Equipment
description: Portable conceptual knowledge of what ships and key equipment (density scanners, TransWarp) are and mean, with per-server stat values introspected into a live game-data store rather than authored here.
tags: [reference, ships, equipment]
timestamp: 2026-07-19T16:11:33Z
---

**Two-layer rule:** this concept authors only portable, server-independent knowledge — what a ship
or piece of equipment IS and what each stat axis MEANS. It intentionally contains NO ship stat
values (no hold/fighter/shield/cost numbers for any named ship) — those vary per server and are
meant to be introspected live into a per-server game-data store (see Schema below), never
hardcoded here. If a value is needed for a decision, read it from that store, not from this
document.

# Ships — what they are
A ship is the player's ownable, upgradeable vessel: a bundle of a cargo capacity, a combat
loadout, a movement cost, and (usually) an alignment/rank gate on who may acquire it. Ships are
typically acquired and upgraded at a StarDock or equivalent shipyard.

# Stat axes — what each one means
- **Holds** — the ship's cargo capacity unit; the ceiling on how much commodity/equipment can be
  carried per trip. The single highest-leverage stat for trading throughput.
- **Fighters** — deployable combat units the ship carries; primary offense and a layer of defense,
  consumed in combat.
- **Shields** — a defense layer that absorbs damage before fighters/hull are touched; generally the
  more efficient defensive investment per credit relative to fighters — see
  [Toll and Defense Math](/strategies/toll-and-defense-math.md) for the combat strategy that
  depends on this.
- **Combat odds** — a per-ship modifier feeding into combat resolution alongside raw fighter/shield
  counts; higher is more favorable in a fight.
- **Turns-per-warp** — how many turns a single warp-hop costs in this ship; varies by ship and
  materially changes the credits-per-turn math for any trade loop — see
  [Pair Trade Loops](/strategies/pair-trade-loops.md) — a ship with more holds but a higher
  turns-per-warp cost is not automatically the better choice.
- **Cost** — the credit price to acquire/upgrade, frequently gated by alignment and/or rank in
  addition to raw credits (a ship can be unaffordable in the alignment/rank sense even when
  affordable in credits).
- **Special abilities** — ship-specific capabilities (e.g., TransWarp-capable) that don't fit the
  numeric axes above.

# Progression and commissioning
Ship access typically progresses along two independent axes: credits (can you afford it) and
alignment/rank (are you commissioned to fly it). A ship can be the numerically-optimal choice on
paper (most holds, cheapest) and still be unavailable because it requires a standing the player
hasn't earned. Progression strategy should weigh both axes, and should weigh the remaining turn
budget of the current session against the amortization time a bigger ship needs to pay for itself
— a large capacity upgrade taken very late in a turn-capped run may not have enough turns left to
earn back its cost.

# Density scanner — what it does
Scans adjacent sectors without entering them, returning a signature that indicates likely contents
(see [Frontier Exploration](/strategies/exploration.md) for the hypothesized value-to-content
mapping and its unverified status). Its economic role is a force-multiplier on exploration: it
turns "visit every sector to see what's there" into "read a signature, then only visit the sectors
worth visiting" — a large efficiency gain for mapping, at zero turn cost per scan.

# TransWarp drive — what it does
Allows a direct jump to any previously-visited sector, bypassing the warp-hop path between here and
there. Its economic role is a turn-savings tool for navigation to a known-distant target (a
shipyard, a far trade loop, a colonization site) — valuable once acquired, but typically an
expensive, later-game acquisition whose worth is a cost/benefit comparison against the turns it
saves, not an early-game default.

# Progression pitfalls (general, non-numeric)
- A large capacity upgrade can outstrip a single small loop's stock — running a big-holds ship
  against a modest port will deplete it faster than the port regrows (see
  [Port Economics](/strategies/port-economics.md)); bigger capacity needs a bigger or chained loop,
  or stock-aware rotation, to actually get used.
- A freshly-upgraded ship commonly arrives with little or no defense (fighters/shields) even though
  it cost significant credits — treat a ship upgrade and its defense loadout as one combined
  decision, not two, especially in any environment with hostile encounters (see
  [Toll and Defense Math](/strategies/toll-and-defense-math.md)).

# Schema
The following is the schema a per-server game-data introspector should populate — field
names/types/semantics only; no values are authored here.

## Ships table
| Field | Type | Semantics |
|---|---|---|
| ship_name | string | This server's name for the ship |
| max_holds | integer | Cargo capacity ceiling |
| max_fighters | integer | Fighter capacity ceiling |
| max_shields | integer | Shield capacity ceiling |
| combat_odds_modifier | number | Per-ship combat-resolution modifier |
| turns_per_warp | integer | Movement cost per warp-hop |
| base_cost_credits | integer | Acquisition/upgrade cost in credits |
| alignment_requirement | number or null | Minimum alignment to acquire, if gated |
| rank_requirement | string or null | Minimum rank/commission to acquire, if gated |
| transwarp_capable | boolean | Whether this ship can mount a TransWarp drive |
| special_abilities | list of string | Any non-numeric special capabilities |
| source | string | How this row was obtained (e.g. "introspected: shipyard listing") |
| last_verified_ts | ISO-8601 datetime | When this row was last confirmed live |

## Scanners table
| Field | Type | Semantics |
|---|---|---|
| scanner_type | string | e.g. density, holographic |
| cost_credits | integer | Acquisition cost |
| capability_notes | string | What it reveals / range, in this server's terms |
| last_verified_ts | ISO-8601 datetime | When this row was last confirmed live |

## TransWarp table
| Field | Type | Semantics |
|---|---|---|
| cost_credits | integer | Acquisition cost |
| range_notes | string | Any range/restriction this server applies |
| last_verified_ts | ISO-8601 datetime | When this row was last confirmed live |

## Items/catalog table (genesis, mines, misc equipment)
| Field | Type | Semantics |
|---|---|---|
| item_name | string | This server's name for the item |
| cost_credits | integer | Acquisition cost |
| effect_notes | string | What it does, in this server's terms |
| last_verified_ts | ISO-8601 datetime | When this row was last confirmed live |

# Citations
[1] design history §22.5 — ships + stats canon requirement: feeds auto-max-holds, coaching, OKF;
    numbers verified vs the live game where they differ from stock TW2002
[2] design history §23 — game introspection meta-principle: portable canon vs live per-server
    data, two-layer split
[3] design history §23.5 — density scanner and TransWarp: what they do and their economic role
[4] design history §24 — ship-progression live-play lessons: turn-budget ROI, alignment/rank
    gating, turns-per-warp variance, capacity-vs-loop-stock matching, defense-vs-holds tradeoff
