---
type: System
title: World Model — the Persisted Per-World Sector Database
description: The incrementally-built per-world map of warps, ports, threats, and landmarks that every routing, guard, and coaching behavior reads — a store read by others, never a store that drives itself.
tags: [world-model, system, sector-database, per-world, prescriptive, pathfinding, read-only-store]
timestamp: 2026-07-23T20:01:54Z
---

The world model is the persisted per-world sector database the trainer accumulates as the human
plays: one record per known sector, holding that sector's warps, its port and last-seen prices,
its threats, its landmarks, and its formation membership. It is the map every higher behavior
stands on — rule-guards read it to decide whether a taught macro is safe to replay here, the
[AI Teacher](/engine/ai-teacher.md) reads it when the human asks it to Analyze an escalation, the
[Coaching Engine](/engine/coaching-engine.md) reads the current sector's neighborhood to surface a
tip, and the [Priority Engine](/engine/priority-engine.md) reads spreads and distances to order
which taught behaviors it suggests. It is the shortest-path substrate under all deterministic
navigation.

The single most important thing to say about it, in the reborn framing, is what it is **not**: the
world model is a store that is *read by* guards, the teacher, and the human — it is never a store
that reads *itself* to drive the ship. Nothing in this module emits a keystroke. It is a passive,
prescriptive knowledge surface: this document describes the store the client's parsers must write
to and the store its planning and coaching behaviors must read from, not any autonomous loop. When
a behavior needs the world model to decide something, that behavior asks the store a question and
gets an answer back; the store never volunteers an action. Live keystrokes come only from the app
replaying a human-taught, human-approved macro, or from the human's own keyboard — and on any
screen the app does not recognize, the app STOPS and hands the human the keyboard. A stale or
missing world-model record is one of the things that can force exactly that STOP-and-escalate,
because acting on a lower-confidence map is a way to send the human's ship somewhere it was never
meant to go.

# Schema

## World identity — the keying rule

The world model is keyed **per world**, never globally. A world is identified by the telnet host
plus the in-game game letter plus the character/handle — all three together, never just
host+game — because a fresh character registration produces a fresh generated galaxy even on the
same game letter. Two different characters on the same nominal game are two different worlds, and
their maps, threats, and learned loops must never bleed into each other. This module treats the
`world_id` as an opaque caller-supplied string and never computes one itself; the single authority
that names a world is [World Identity](/engine/world-identity.md). A store keyed only by host+game
risks exactly the cross-galaxy collision that would replay one galaxy's map into another.

## Sector record

One record per known sector:

| Field | Type | Notes |
|---|---|---|
| `sector_id` | int | The sector number; the record's key within a world (the required field on every write). |
| `warps` | list[int] | Outbound sector links — the graph edges pathfinding and formation detection read. |
| `port` | object \| null | `{class, commodities: [{name, status(buying/selling), amount, pct}], last_seen_ts}` — the price database trade-loop and chain discovery read spread from. `null` means "observed to have no port," distinct from an absent field ("not yet observed"). |
| `threats` | object | `{mines: bool, fighters: {count, owner} \| null}` — the hazard database routing avoids and toll-math reads fighter counts from. |
| `landmarks` | list[string] | e.g. `stardock`, `class_zero`, `own_planet`, `ferrengi` — locations worth caching once found rather than rediscovering. |
| `formation_membership` | list[string] \| null | Which detected special-formation(s) — dead-end, bubble, one-way, warp-sink — this sector belongs to. |
| `last_seen_ts` | ISO-8601 | Staleness marker — fighters move and prices drift, so a stale record is a lower-confidence one, not a false one. |

## Persistence and upsert semantics

The store is **one file per sector** — `state/world/<world_id>/sectors/<sector_id>.json` — not one
file per world. Per-sector files make a single-sector write O(1) (only that file is read and
rewritten) and give the `fcntl.flock` per-sector scope, so two writers touching *different* sectors
in the same world never contend. Cross-world isolation is structural: two worlds never share a
directory, so they cannot bleed into each other regardless of any bug. Writes are atomic
(temp-then-rename, chmod 0600) so a crash mid-write can never corrupt an existing record; a corrupt
or wrongly-shaped file is a fatal, named error, never a silent reset to an empty sector (that would
be data loss dressed as recovery).

Upserts are **field-level, additive, last-write-wins per field**. A write may be partial — only
`sector_id` is required. A top-level field present in the incoming record *fully replaces* the
stored field (an old and new `port` commodities list are never unioned; the new one wins outright,
per "supersedes rather than merges stale and fresh data"). A field *absent* from the write is left
untouched — a warps-only write from a plain move must not erase previously-learned port data for
that sector. The one nested exception is `port`: when the incoming `port` is a dict, its own
sub-fields (`class`, `commodities`, `last_seen_ts`) get the same additive treatment one level
deeper, so an ordinary port visit that observes commodities but never a `class` does not clobber a
`class` a prior batch scan already learned. An explicit `port: null` is still an unambiguous
wholesale "this sector has no port, clear it" reset.

`last_seen_ts` **always advances on a genuine observation** — every upsert re-stamps it, even when
the merge is otherwise a content no-op. It is the canon's "I was actually here, this recently"
staleness marker that a future freshness/rescan policy needs to stay honest; freezing it on an
unchanged re-observation would silently lie about freshness.

# Ingestion

The world model has no acquisition step of its own — it is populated from screens the client
already parses. Reading is what fills it; the store is never the actor. The write paths, ordered
turn-free-first (the cheaper the game-turn cost, the more preferred):

- **Batch port/sector report (turn-free bulk).** A single screen listing many sectors at once — a
  CIM (Computer Interrogation Mode) port report or a multi-sector scan — writes many records in one
  `bulk_upsert` pass. Parsing is by *anchored per-line regex*, never fixed-column: each data row is
  matched for its sector number, its three-letter Buy/Sell port class code (`Class: XXX`), its
  `F:% O:% E:%` percentages, and its `Warps: n-n-n` list, and only the fields a row actually encodes
  are written — never a guessed field, never a garbage record for a row that can't be confidently
  anchored (silently skipped instead). The report block is anchored to the LAST header/footer pair
  in the buffer, the same stale-scrollback discipline every field in this project uses (see
  [Screen Understanding](/engine/screen-understanding.md)).
- **CIM bulk scrape.** The same batch path fed by a full Computer Interrogation Mode dump — the
  fastest way to fill a large slice of the map, when the human has run it.
- **Density / holographic scan (turn-free adjacent-contents read).** A density scan reads the
  *contents* of adjacent sectors without physically entering each one. Its numeric density values
  are interpreted against a value table (see Verification status) into presence facts —
  approximately `1=beacon · 5=fighter · 10=mine · 40=ship · 100=port/StarDock · 500=planet` — which
  become `port`/`threats` writes on the scanned sectors. Fighter presence can also be inferred by
  *absence* of the expected empty-sector reading. Both the value table and the presence-via-absence
  inference are unverified and must be treated as provisional.
- **Plain per-visit state read (one turn per sector).** Every parsed game-state read (the sector
  status line: its warps, its `Ports :` flyby line, its mine/fighter tells) writes that sector's
  `warps`/`port`/`threats`. This is the slowest fill path — one physical warp per new sector — and
  the fallback when no turn-free report is available.
- **Docked commerce-report port write.** A docked port's commodity report carries no "Sector : N"
  line of its own, so its sector is resolved from that same screen's trailing ship Command prompt
  and its `commodities` written for that explicitly-supplied sector — reusing the existing commodity
  extraction, never a second row parser.

Every write is additive and last-seen-stamped; `landmarks` and `formation_membership` are written
by dedicated passes (exploration, the formation detector), not by a raw state read, so a plain visit
never clears them.

**How that guarantee is enforced (2026-07-28, `WO-WM-LANDMARKS-WRITE`).** "A plain visit never
clears them" was, until now, a rule a writer had to *remember*: `write_from_state` maps only
`warps`/`port`/`threats` and silently drops a `landmarks` key, so the raw state read could not
clear a landmark — but any pass writing through `upsert_sector` could, because that field replaced
like every other. It is now structural instead: **`landmarks` is the one field whose upsert
UNIONS.** No record passed to `upsert_sector` can shrink a sector's landmark set, so an
observation that merely failed to notice can never erase one that did.

The asymmetry is not arbitrary. Every other field has a screen that can *deny* it — `Ports : None`
positively states there is no port — whereas nothing the trainer can read says "there is positively
no landmark here". A sector display that does not mention StarDock is **silence, not a denial**, and
silence must not be allowed to write. Removal, if a landmark is ever found to be genuinely wrong,
owes its own deliberate path and an observation that can justify it; neither exists today, and
inventing one would be the same guess in the opposite direction.

Consequently a landmark-writing pass calls `upsert_sector` **directly** with
`{sector_id, landmarks: [...]}`, and only when something was actually observed — it does not route
through `write_from_state`, whose refusal to carry the field is deliberate and stays.

**The named writer (2026-07-28, `WO-LANDMARK-ATTRIBUTE-LAST-KNOWN`).** That "calls `upsert_sector`
directly" is now spelled `add_landmark(world_id, sector_id, name)`, and it is the **only**
product-facing way into the field. Until it existed the guarantee above protected a field **nothing
in the product ever wrote** — `write_from_state` was the single product write path and it declines
landmarks, so the union semantics were correct and unreached.

Two properties of that writer are load-bearing rather than stylistic:

- **The caller supplies the sector; the writer never guesses it.** Because the field unions and has
  no removal path, a wrong attribution is permanent — so the question "do we know where we are?"
  belongs to the layer that can actually answer it, and arrives already decided.
- **Junk raises rather than returning a quiet negative.** A bad type is a programming error, and a
  silent `None` would be indistinguishable from the caller's legitimate *"we do not know the sector,
  do not write"* — the one signal that has to stay readable.

Which sector a sector-less screen belongs to is decided by the landing-screen rule in
[session-engine](/architecture/session-engine.md), not here.

# Consumers

Everything here **reads** the store; none of it lets the store drive.

- **Rule-guards.** Before a taught macro replays, its guard reads the world model for the state that
  proves replay is safe *here* — the sector matches, the expected port is present, no unexpected
  hazard. The store supplies the guard's evidence; the [Rule–Macro Engine](/architecture/rule-macro-engine.md)
  and the app's stop-on-unknown discipline decide what to do with it. A stale or missing record can
  make a guard refuse and force STOP-and-escalate rather than replay on a lower-confidence map.
- **The pathfinding primitive.** Shortest-path over the `warps` graph is the nav under everything —
  routing to a target sector, StarDock runs, formation approaches, deterministic menu navigation,
  trade-chain hops. It is a plain BFS over the known subgraph; it never invents a warp it hasn't
  observed, and it returns a path or nothing, never a guess. Callers walk one adjacent hop at a time,
  re-planning each tick, rather than committing a whole path blindly.
- **Auto-explore.** Frontier/BFS planners read the graph to find edges to not-yet-mapped neighbors
  and read cached landmarks ("is the StarDock already known?") before proposing where to look next.
  They propose the next hop; they never emit the keystroke (see
  [Exploration Policy](/strategy/exploration-policy.md)).
- **Formation detector.** A pure topology pass over the `warps` graph flags dead-ends, bubbles,
  one-ways, and warp-sinks and writes `formation_membership` back — LOCATE / CATALOG / RECOMMEND
  only, never a Genesis deploy or a claim (see [Special Formations](/strategy/special-formations.md)).
- **AI Teacher (retrospective, human-invoked).** When the human asks the teacher to Analyze an
  unrecognized screen or an escalation, the teacher reads the current sector's world-model context to
  ground the guarded rule it *drafts* — it is a rule author, never a live keystroke.
- **Coaching Engine.** Reads the occupied sector and its neighbors to surface the best option and its
  tradeoffs — a good trade at this port, a defensible dead-end nearby, a toll's fighter count for
  attack/pay/flee math. It teaches the option; it never fires it.
- **Priority Engine.** Reads spreads and travel distances to rank *what to pursue* and to order which
  taught behaviors it suggests — never to pick a live action over an unknown screen.
- **TUI metrics.** Headline counts (stations found, planets found, fighters/mines encountered,
  problematic sectors) are a live view *over* the accumulated world model, not a separately-tracked
  tally.

## Staleness and freshness discipline

Because prices drift and fighters move, `last_seen_ts` is confidence, not truth: an old record is
lower-confidence, not false. A consumer that needs current data (a guard about to authorize a
value-bearing replay, a chain that assumes a spread) weighs freshness and, when a record is too stale
to trust, the safe outcome is STOP-and-escalate — hand the human the keyboard — never act on a guess
and never silently re-derive by pressing an ACTION key. Re-freshening a stale record is a read
(re-scan, re-visit), and any ACTION-class step it might touch is gated exactly like any other rule.

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
    "last_seen_ts": "2026-07-23T00:00:00Z"
  },
  "threats": {"mines": false, "fighters": null},
  "landmarks": [],
  "formation_membership": ["dead-end"],
  "last_seen_ts": "2026-07-23T00:00:00Z"
}
```

# Verification status

- **VERIFIED (grounded in code / real captures):** the sector record schema and its field-level
  upsert semantics (`world_model.py`); per-world keying = host + game-letter + character
  (`world_identity.py`); the plain per-visit `warps`/`port`/`threats` write from a parsed sector
  status line and the docked commerce-report port write (`world_model.py`, `write_from_state` /
  `write_port_only`, fed by `state_parser.parse_state` / `parse_port_report`); shortest-path BFS
  over the warp graph (`explore.py`, `path_to_sector`); the
  formation topology pass (`formations.py`).
- **HYPOTHESIS (constructed, not yet live-captured):** the CIM/batch port-report row grammar
  (`-=-=- Port Report (CIM) -=-=-` header/footer, `Sector N  Class: XXX  F:N% O:N% E:N%  Warps:
  n-n-n` rows) in `parse_port_report` — constructed from the independently-verified three-letter
  Buy/Sell class convention plus this project's own real-capture divider style; and the density-scan
  value table (`1=beacon · 5=fighter · 10=mine · 40=ship · 100=port/StarDock · 500=planet`) and the
  fighter-presence-via-absence inference. Concrete per-server numbers are never hardcoded in canon —
  they are introspected live (see [Game-Data Store](/engine/game-data-store.md)); this document
  authors portable semantics and schemas only. Consumers must treat all three as provisional until a
  live capture confirms them, and each should carry its own inline caveat wherever it is consumed.

# Code divergence

The store modules are faithful to the reborn target — they are pure read/write persistence and
planning surfaces that never emit a keystroke, so the "read by others, never self-driving" invariant
holds structurally. Two things worth recording:

- **The batch/CIM and density-scan ingestion paths are partly unlanded against a live game.**
  `parse_port_report` exists and is unit-tested, but no live multi-sector CIM/scan screen has been
  captured yet, so its row grammar is a hypothesis (above). **Tip (WO-BUILD-DENSITY-SCAN-VALUE-TABLE-PARSER):**
  `tw2002_aiclient.density_scan.parse_density_scan` + `DENSITY_VALUE_TABLE` land the raw
  `sector → density` extract and the canon atom table; row grammar remains a **hypothesis** (synthetic
  fixtures only — no live multi-sector density screen capture yet). World-model writeback /
  presence-via-absence decoding are **still unlanded** — this is an interpreter kernel, not an
  ingestion path. Recorded as a residual build gap (writeback), not a behavioral defect.
- **`formations.py` membership writeback is wired** (WO-FORMATIONS-MEMBERSHIP-WRITEBACK / #326).
  `catalog_world` and `WorldStats.refresh` call `write_membership` after a successful scan, stamping
  canon-hyphen `formation_membership` tags. Still LOCATE/CATALOG/RECOMMEND-only — no Genesis or claim
  action. `recommend_genesis` remains an alias of `genesis_candidates` without a separate auto-caller.
  Route-hazard STOP/exclude for explore/trade is also wired (#327–#329); see
  [Special Formations](/strategy/special-formations.md) § Code reality.

# Citations

- design history §15.0 / §15.3 — the world-model schema and the dependency spine (the load-bearing
  wall every higher behavior reads).
- design history §20 — the per-game-world keying correction (host + game-letter + character).
- design history §23 — game introspection as a sibling per-world knowledge store.
- `world_model.py` — persistence layout, field-level and nested-port upsert semantics, the
  always-advance `last_seen_ts` ruling.
- `explore.py` — frontier BFS, shortest-path (`path_to_sector`) pathfinding primitive, exhausted-frontier recovery.
- `state_parser.py` — the last-match anchoring discipline, the plain-visit and batch/CIM write mappings.
- `formations.py` — the topology catalog (dead-end / bubble / one-way / warp-sink), membership writeback, and `route_hazard_for_hop`.
- canon/research/archive-port-patterns.md AP-06 (per-sector file layout, fcntl lock scope, atomic
  rename pattern, field-level and nested-port merge algorithms, write_from_state class-omit rule).
