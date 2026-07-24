---
type: Reference
title: Special Formations — Topology Detection & Response
description: Warp-graph topology detection (dead-end, bubble, one-way, warp-sink) that feeds route-hazard guards and colonization-siting recommendations, under a strict LOCATE-CATALOG-RECOMMEND boundary.
tags: [topology, world-model, formations, genesis, colonization, route-hazard, autonomy-boundary]
timestamp: 2026-07-23T20:19:59Z
---

A **special formation** is a *topology* pattern in the mapped warp graph — a shape the
sector-to-sector warp connections form, independent of what any individual sector contains.
Formations are found by walking the graph the app has already built through ordinary play;
recognizing one never requires visiting every sector inside it.

The detector is a **world-model consumer** with a single, strict output posture: it LOCATES,
CATALOGS, and RECOMMENDS — it surfaces topology facts to the operator and to the ranking layers,
and it never acts on them. Deploying a Genesis device or claiming space is always an
operator-confirmed action. This concept is the classification-and-response spec; the graph store
it reads is owned by [world-model](/engine/world-model.md), and the human-approval boundary it
honors is owned by [control-and-escalation](/architecture/control-and-escalation.md).

# Cluster vs. Formation

Two different ideas travel under "region" in TW play; the app keeps them distinct:

- A **cluster** is a *biome* — a neighborhood grouped by what its sectors *contain* (a band of rich
  ports, a mined region, a Ferrengi patch). It is a content grouping.
- A **formation** is a *graph shape* — a pattern in how warps *connect*, independent of contents.
  A dead-end is a dead-end whether it hides a planet or an empty sector.

Everything below is about formations — pure graph topology. Content-based reasoning (port quality,
threat density) lives in [port-economics](/strategy/port-economics.md) and the density-scan table
in [exploration-policy](/strategy/exploration-policy.md); it is a separate axis the detector does
not touch.

# Schema

## The four topology flags

| Formation | Graph shape | Class | Why it matters |
|---|---|---|---|
| **Dead-end** | A sector with a single warp (one way in, same way out) | Siting candidate | One approach vector — easy to defend; a strong candidate for hiding a planet or cache |
| **Bubble** | A sealed pocket (≥2 interior sectors) reachable only through one entrance sector | Siting candidate | Isolated, low-traffic — a defensible hideout or safe production pocket |
| **One-way warp** | A warp traversable in only one direction (A→B with no B→A) | Route hazard | Enter but cannot backtrack the same route — a navigation trap |
| **Warp sink** | A sector or small cluster reachable via inbound warps but with no outbound path back to open space | Route hazard | The severe hazard variant — traffic accumulates and cannot leave by warp alone |

The detector emits a catalog of `Formation` records — `{kind, sectors, entrance, detail}` — plus a
`genesis_candidates` shortlist (the dead-ends and bubbles) and a `known_sectors` coverage count.
The `entrance` field names the single approach sector for a bubble or dead-end. Membership can also
be written back onto each sector's `formation_membership` field in the world-model (see Code reality
below).

## The topology-pass mechanism (G3 / TW-16)

Detection is a **pure topology pass over the already-mapped warp graph** — it does not itself drive
exploration. As the world-model accumulates sectors and warps from ordinary play (density scans, CIM
reports, manual navigation), the graph store is walked to compute per-sector in/out-degree and
reachability, and sectors matching the shapes above are flagged. Concretely:

- **Dead-ends** — any sector whose recorded warp list has exactly one outbound edge.
- **Bubbles** — for each candidate entrance sector, grow the component reachable from a neighbor
  *without traversing the entrance*; if every edge leaving that component lands only back on the
  entrance and the entrance has exactly one other door to the open map, it is a sealed pocket. The
  smaller side of the cut is taken (so the open "outside" is never mislabeled), and only the
  innermost pocket is kept when pockets nest.
- **One-way warps** — a recorded edge A→B where B's warp list does not contain A.
- **Warp sinks** — sectors that have inbound reachability from some other known sector but cannot
  reach that sector back (a trap), clustered into connected formations; pure dead-ends are not
  double-labeled as sinks.

Because it reads only what has been mapped, the detector is **coverage-bounded**: it improves as the
map fills and never asserts a formation over unmapped space. A warp to an as-yet-unknown sector is
skipped by the undirected/pocket math until both ends are known; only the directed one-way pass reasons
across a half-known edge. This makes the pass a consumer of [world-model](/engine/world-model.md) and
[exploration-policy](/strategy/exploration-policy.md)'s map-fill, not a parallel exploration behavior —
it plans nothing, sends nothing, and reads no live screen.

# Dual consumer split

A formation flag flows to exactly one of two downstream layers, by class — and in both cases it is an
**input to ranking or guarding, never a trigger to act**:

- **Route hazards → guard inputs.** One-way warps and warp sinks are hazards to route *around*. They
  feed the guard predicates a navigation/routing behavior checks before it moves: a route that would
  cross a known one-way warp or enter a known warp-sink is exactly the kind of thing a guard blocks —
  the guard STOPS and hands the keyboard to the human rather than committing to the trap. This is the
  same never-fire-unverified contract enforced in
  [action-safety-guards](/doctrine/action-safety-guards.md); the hazard flag is a *fact the guard
  reads*, and the STOP carries a typed reason-code (a route-hazard is a `hazard` escalation per the
  [control-and-escalation](/architecture/control-and-escalation.md) catalog).
- **Siting candidates → colonization-recommendation inputs.** Dead-ends and bubbles are defensible,
  low-traffic sites. They feed the candidate scoring in
  [planet-colonization](/strategy/planet-colonization.md), where the priority layer *ranks and orders*
  siting recommendations for the operator to review. Ranking a dead-end highly is the ceiling of the
  detector's influence — the priority layer orders which recommendations the human sees; it never lets
  a high site-score pick a live action, and Genesis deploy remains a human-confirmed one-shot.

Note the deliberate asymmetry: the priority layer *ranks* siting candidates, but it does **not**
autonomously site anything, and route-hazard flags feed *guards that STOP*, never an autonomous
reroute-and-continue. In neither direction does a computed score or a topology fact override
stop-on-unknown or the human-approval gate.

# Standing Rule

The standing rule is stated verbatim and is non-negotiable:

> **The trainer LOCATES, CATALOGS, and RECOMMENDS — nothing more.** Flagging a formation and
> suggesting it as a Genesis candidate is as far as it goes. Deploying a Genesis device or claiming
> contested space is always an **operator-confirmed action** — the trainer never does either on its
> own, no matter how strong the candidate looks.

Cataloging is a standing "tick to locate" behavior the operator can arm; acting on the catalog is a
separate, explicit decision every time. The detector surfaces to the human and to the ranking layers,
and it never acts. See [alignment-and-conduct](/doctrine/alignment-and-conduct.md) for the same
operator-confirmation posture applied to combat, and
[planet-colonization](/strategy/planet-colonization.md) for the human-gated Genesis deploy the siting
recommendation ultimately feeds.

# Examples

```
Coaching surface, after a mapping pass:

  Dead-end flagged at sector <N> — single warp in/out, no other traffic observed.
  Genesis candidate: defensible, low-visibility. Catalog only — take no action
  without confirmation.

  Bubble flagged (entrance <E>, interior <N>..<M>) — single-entrance pocket.
  Genesis candidate: isolated, safe production. Catalog only — confirm to act.

  One-way warp <A>→<B> flagged — no reverse warp found. Route hazard: a routing
  guard will STOP here rather than cross unless the operator takes the keyboard.

  Warp sink flagged at sector <M> — inbound warps only, no outbound path to open
  map. Severe route hazard: avoid unless intentional.
```

# Code reality

- The detector is `formations.py` — `detect_formations(graph)` is the pure topology pass
  (`_dead_ends` / `_bubbles` / `_one_ways` / `_warp_sinks`), and `catalog_world(world_id)` runs it over
  the warp graph supplied by `explore.known_graph` (which reads `world_model`). This matches the reborn
  contract as written: LOCATE / CATALOG / RECOMMEND, no Genesis or claim action anywhere in the module.
- **Code reality (defined-but-unwired, no divergence from the reborn target):** the world-model
  writeback trio — `membership_map`, `write_membership` (upserts `formation_membership` onto each
  sector), and `recommend_genesis` (the operator-facing shortlist, identical to
  `catalog.genesis_candidates`) — is **parked** (WO-FA14, 2026-07-23): unit-tested, optional-by-design,
  with no production caller yet. Live spectate/explore call only `catalog_world`. This is a wiring gap,
  not a doctrine divergence — the parked functions are catalog-only side effects that still take no
  Genesis or claim action, fully consistent with the standing rule. Recorded here so the gap is visible,
  not silently conformed.

# Citations

- Design history §12 — game context and the Special-Formation detector.
- Design history §15.5 — Special-Formation detector and Genesis appetite (recast under the reborn
  vision: the appetite becomes a priority-ranking input to human-confirmed siting, not an autonomous
  Genesis driver).
- Code: `formations.py` (topology pass, catalog, parked writeback trio), `explore.py` (`known_graph`),
  `world_model.py` (`warps`, `formation_membership`, per-world sector store).
- Cross-cutting map — OKF Final Vision Map, `strategy/special-formations.md` section and Operator
  rulings (RESOLVED 2026-07-23): planet-colonization and special-formations kept separate because
  formations feeds a route-hazard guard consumer colonization lacks.
