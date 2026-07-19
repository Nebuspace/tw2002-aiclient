---
type: System
title: World Model — the Persisted Sector Database
description: A per-world, per-sector knowledge store of warps, ports, threats, and landmarks that every exploration, coaching, and routing behavior reads from.
tags: [world-model, system, prescriptive, sector-database]
timestamp: 2026-07-19T16:12:01Z
---

The world model is the persisted sector database the trainer builds as it plays, and the
foundation every higher-level behavior stands on: routing, trade-loop discovery, exploration,
formation detection, and coaching all read this store rather than re-deriving the map from
scratch each time. This concept is prescriptive — it describes the store the client's parsers
must write to and the store its planning behaviors must read from, not a report of what has
already been wired.

# World Identity — the keying rule

The world model is keyed per **world**, not globally: a world is identified at minimum by the
telnet host plus the in-game game letter, and in practice also by the character/registration,
because a fresh character registration produces a fresh generated galaxy even on the same
game letter. Two different characters registered on the same nominal game are two different
worlds, and their maps, threats, and learned loops must never bleed into each other. Any store
keyed only by host+game risks exactly this collision.

# Schema

One record per known sector:

| Field | Type | Notes |
|---|---|---|
| `sector_id` | int | The sector number; the record's key within a world. |
| `warps` | list[int] | Outbound sector links — the graph edges pathfinding and formation detection read. |
| `port` | object \| null | `{class, commodities: [{name, status(buying/selling), amount, pct}], last_seen_ts}` — the profit database; trade-loop and chain discovery read commodity spread from here. |
| `threats` | object | `{mines: bool, fighters: {count, owner} \| null}` — the threat database; routing avoids hazards here, toll-math reads fighter counts here. |
| `landmarks` | list[string] | e.g. `stardock`, `class_zero`, `own_planet` — locations worth caching once found rather than rediscovering. |
| `formation_membership` | list[string] \| null | Which detected special-formation(s) (dead-end, bubble, tunnel, warp-sink, …) this sector belongs to. |
| `last_seen_ts` | ISO-8601 | Staleness marker — fighters move and prices drift, so a stale record is a lower-confidence one, not a false one. |

# Write Hooks

The world model is populated incrementally from screens the client already parses — it has no
separate acquisition step of its own:

- Every parsed game-state read (sector, port commodities) writes its sector's `port`/`threats`
  fields.
- A batch port/sector report (a single screen listing many sectors at once) writes many sector
  records in one pass rather than one per visited sector — the store must accept bulk writes,
  not only single-sector updates.
- A dedicated exploration pass (density-scan or CIM-style bulk scan) writes adjacent-sector
  contents without the client having to physically enter each sector.

Each write is additive and last-seen-stamped; a later write to the same sector supersedes the
earlier one rather than merging stale and fresh data.

# Consumers

- **Auto-explore** — frontier/BFS behaviors that write new sectors in, and read known landmarks
  (e.g. "is the StarDock already cached?") before deciding where to explore next.
- **Formation detector** — a topology pass over the `warps` graph that flags dead-ends, bubbles,
  tunnels, and warp-sinks, writing `formation_membership` back into the sectors it identifies.
- **Trade-loop / chain discovery** — reads `port` commodity spreads across the graph to find
  profitable multi-hop chains, ranked by profit-per-turn.
- **Coaching** — reads the sector the operator currently occupies (and its neighbors) to surface
  contextual advice: a good trade at the current port, a defensible dead-end nearby, a toll's
  fighter count for attack/pay/flee math.
- **TUI metrics** — headline counts (stations found, planets found, fighters encountered, mines
  encountered, problematic sectors) are a live view over the accumulated world model, not a
  separately-tracked tally.

# Examples

```json
{
  "sector_id": 4242,
  "warps": [4241, 4243, 917],
  "port": {
    "class": "BBS",
    "commodities": [
      {"name": "Equipment", "status": "selling", "amount": 18000, "pct": 100}
    ],
    "last_seen_ts": "2026-07-19T00:00:00Z"
  },
  "threats": {"mines": false, "fighters": null},
  "landmarks": [],
  "formation_membership": null,
  "last_seen_ts": "2026-07-19T00:00:00Z"
}
```

# Citations

[1] design history §15.3 (the world model schema and dependency spine)
[2] design history §15.0 (the spine diagram — world model as the load-bearing wall)
[3] design history §20 (per-game-world keying correction)
[4] design history §23 (game introspection as a sibling per-world knowledge store)
