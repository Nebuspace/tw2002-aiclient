---
type: Doctrine
title: Special Formations — Detection & Response Doctrine
description: How the trainer identifies warp-graph topology anomalies (dead-ends, bubbles, one-way warps, warp-sinks) and the strict operator-confirmation boundary on acting upon them.
tags: [world-model, topology, genesis, autonomy-boundary]
timestamp: 2026-07-19T16:11:17Z
---

A **special formation** is a *topology* pattern in the mapped warp graph — a shape the sector-to-sector
warp connections form, independent of what any individual sector contains. Formations are detected by
walking the graph the client has already built through exploration; nothing about them requires
visiting every sector in a formation to recognize it.

# Formation Types

| Formation | Graph shape | Why it matters |
|---|---|---|
| **Dead-end** | A sector with a single warp (one way in, same way out) | Easy to defend — one approach vector; a strong candidate for hiding a planet or cache |
| **Bubble** | A sealed pocket reachable only through one narrow entrance | Isolated, low-traffic — good for safe farming or a defensible hideout |
| **One-way warp** | A warp that is traversable in only one direction | A navigation hazard — ships can enter but not backtrack the same route |
| **Warp sink** | A sector (or small cluster) reachable via one-way warps but with no outbound path back to open space | The most severe hazard variant — traffic accumulates and cannot leave by warp alone |

# Why They Matter

- **Defensibility.** A single-entrance topology (dead-end, bubble) narrows the attack surface to one
  approach — valuable for anything worth protecting.
- **Hideouts.** The same narrowness that helps defense also hides activity from casual passers-through.
- **Genesis-candidate sites.** A dead-end or bubble is exactly the kind of defensible, low-traffic
  location worth flagging as a potential site to found a new planet.
- **Navigation hazards.** One-way warps and warp sinks are worth flagging in the opposite direction —
  as risks to route around, not opportunities.

# Detection Approach

The detector runs a topology pass over the *already-mapped* warp graph — it does not itself drive
exploration. As the client's world-model accumulates sectors and warps from ordinary play (scanning,
CIM reports, manual navigation), the graph store is walked to compute per-sector warp in/out-degree
and reachability, and sectors matching the shapes above are flagged. This makes the detector a
consumer of the world-model, not a parallel exploration behavior — it depends on the warp-graph store
and pathfinding already existing, and improves in coverage as the map fills in.

# Standing Rule

**The trainer LOCATES, CATALOGS, and RECOMMENDS — nothing more.** Flagging a formation and suggesting
it as a genesis candidate is as far as autonomy goes. Deploying a Genesis device or claiming contested
space is always an **operator-confirmed action** — the trainer never does either on its own, no matter
how strong the candidate looks. Cataloging is a standing "tick to locate" behavior the operator can
enable; acting on the catalog is a separate, explicit decision every time. See
[paladin-ethos](/doctrine/paladin-ethos.md) for the same operator-confirmation posture applied
to combat.

# Examples

```
Coaching surface, after a mapping pass:

  Dead-end flagged at sector <N> — single warp in/out, no other traffic observed.
  Genesis candidate: defensible, low-visibility. Catalog only — take no action
  without confirmation.

  One-way warp sink flagged at sector <M> — entry warps only, no outbound path
  found. Route hazard: avoid unless intentional.
```

# Citations

[1] design history §12 — Game context + Special-Formation detector
[2] design history §15.5 — Special-Formation detector + genesis appetite
