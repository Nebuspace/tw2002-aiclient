---
type: System
title: Game-Data Store — Portable Semantics vs. Live Per-Server Introspected Data
description: A two-layer knowledge store — this bundle authors only portable, server-independent semantics and schemas, while concrete per-server stat values are introspected live and never hardcoded in canon.
tags: [game-data, introspection, two-layer, per-world, ships, equipment, read-only, invariant]
timestamp: 2026-07-23T20:01:50Z
---

Every decision the trainer helps the human make about a ship, a scanner, a TransWarp drive, or a
piece of ordnance eventually needs a *number*: how many holds this ship carries, what the next hold
costs, whether the player's alignment even lets them commission it. Those numbers are **not**
universal. TradeWars servers re-tune ship stats, prices, and gates; a value that is right on one
server is wrong on the next. So this concept draws a hard line down the middle of "game data": the
portable half — *what a ship is, what a stat axis means, what a density scanner does* — is authored
here, once, and carries no values; the concrete half — *this server's holds, this server's price,
this server's alignment gate* — is read off the live game screen into a per-world store and is
**never** written into canon.

That split is not a tidiness preference. It is a safety-and-correctness invariant. A hardcoded stock
number that silently disagrees with the live server would feed a wrong figure into an upgrade-ROI
calculation or a ship-progression suggestion the human is trusting — a bad-spend decision dressed up
as authored fact. The store exists precisely so that no such number can enter the system except by
having been read from the game itself.

And — the reborn framing that governs every store in this bundle — the game-data store is a thing
that is **read**, never a thing that **drives**. Guards read it to check whether a taught behavior's
preconditions hold; the retrospective AI teacher reads it when proposing a rule draft; the coaching
engine reads it to explain an option's tradeoffs; the human reads it directly. The store never reads
*itself* to pick an action. It is a fact table, not an agent.

# Schema

## The two-layer rule (the load-bearing invariant)

There are exactly two layers, and they never mix:

- **Layer A — portable SEMANTICS (authored here / in the ships-and-equipment reference).** What a
  ship is, what each stat axis *means*, what a density scanner or TransWarp drive *does* and its
  economic role. Server-independent. **Contains no stat values** — no hold count, fighter count,
  cost, or gate for any named ship, on any server.
- **Layer B — introspected DATA (read live into a per-world store).** The concrete rows: this
  server's `max_holds`, `base_cost_credits`, `alignment_requirement`, per-hold upgrade price, and so
  on — each one obtained by *reading it off a live game listing*, each stamped with where it came
  from and when it was last confirmed.

The seam between the two is enforced mechanically, not just by convention. Every Layer-B row carries
a `source` field, and the store **rejects any row whose `source` does not begin with
`introspected`** — a static-authored or guessed number cannot be persisted at all. This gate runs on
the **write** path (before the store is ever touched) *and* on the read/load path, so a hand-edited
value that slipped into the on-disk file is refused on load rather than trusted. "Where a decision
needs a value, read it from the store, not from canon" is therefore not a request — the store
structurally cannot hold a value that wasn't introspected.

## Introspected schema — the row shapes (Layer B)

The store keeps four catalogs plus one singleton quote, all **VIEW-only**: they describe what is
*available* to acquire, obtained by *looking at* a listing. Reading a catalog is never buying from
it — see the read-only acquisition contract below.

**Ships** — one row per ship the shipyard lists:

| Field | Type | Semantics |
|---|---|---|
| `ship_name` | string | This server's name for the ship |
| `max_holds` | integer | Cargo-capacity ceiling |
| `max_fighters` | integer | Fighter-capacity ceiling |
| `max_shields` | integer | Shield-capacity ceiling |
| `combat_odds_modifier` | number | Per-ship combat-resolution modifier |
| `turns_per_warp` | integer | Movement cost per warp-hop in this ship |
| `base_cost_credits` | integer | Acquisition/upgrade cost in credits |
| `alignment_requirement` | integer or null | Minimum alignment to commission, or null if ungated |
| `rank_requirement` | string or null | Minimum rank/commission, or null if ungated |
| `transwarp_capable` | boolean | Whether this ship can mount a TransWarp drive |
| `special_abilities` | list of string | Non-numeric special capabilities |
| `source` | string | How the row was obtained — must begin with `introspected` |
| `last_verified_ts` | ISO-8601 datetime | When the row was last confirmed live |

**Cargo-hold upgrade price** — a *singleton* row (`cost_per_hold`, `source`, `last_verified_ts`),
**not** a name-keyed catalog. The game quotes a per-hold expansion price for the ship the player
currently *has in hand*, not a browsable table for ships they don't own; there is no current-ship
introspection to key it more finely, so the store keeps exactly one such quote per world under a
fixed singleton key. The consumer (an upgrade-ROI scheduler) must treat a missing quote as *unknown,
skip the upgrade branch* — never substitute a guess.

**Scanners** — `scanner_type`, `cost_credits`, `capability_notes`, `source`, `last_verified_ts`.
**TransWarp** — `cost_credits`, `range_notes`, `source`, `last_verified_ts` (no name field: the
label on the listing is decorative). **Items/ordnance** (genesis torpedoes, mines, misc devices) —
`item_name`, `cost_credits`, `effect_notes`, `source`, `last_verified_ts`.

Two write-discipline rules apply across every catalog: a **row supersedes wholesale** — persisting
the same key again (a fresher capture) replaces the prior row rather than sub-merging stale and
fresh fields, because one capture (one shipyard listing) is always a whole, self-consistent
snapshot, never a partial one; and a **field the listing doesn't actually show is omitted or left
null, never guessed** — an unparseable line is skipped rather than turned into a garbage row.

## Portable semantics — what these things ARE (Layer A, no numbers)

The concepts each stat axis and each device denote, authored once and reused across servers, live in
the companion ships-and-equipment reference and are summarized here as the vocabulary the store's
fields name:

- **A ship** is the player's ownable, upgradeable vessel — a bundle of cargo capacity, a combat
  loadout, a movement cost, and (usually) an alignment/rank gate on who may fly it, acquired and
  upgraded at a StarDock-class shipyard.
- **Holds** are the cargo-capacity unit — the ceiling on how much can be carried per trip, the
  single highest-leverage axis for trading throughput. **Fighters** are deployable combat units,
  primary offense and a defensive layer, consumed in combat. **Shields** absorb damage before
  fighters/hull are touched. **Combat odds** is a per-ship modifier feeding combat resolution.
  **Turns-per-warp** is the per-hop movement cost, which varies by ship and reshapes the
  credits-per-turn math of any loop. **Cost** is the credit price, frequently gated by alignment
  and/or rank *in addition to* credits — a ship can be unaffordable in the standing sense while
  affordable in the credit sense.
- **A density scanner** reads adjacent sectors without entering them, returning a signature that
  indicates likely contents — a force-multiplier on exploration ("read a signature, then visit only
  what's worth visiting") at zero turn cost per scan.
- **A TransWarp drive** jumps directly to any previously-visited sector, bypassing the hop path — a
  turn-savings tool for reaching a known-distant target, typically an expensive later-game
  acquisition whose worth is a cost/benefit comparison against the turns it saves.

None of the above states a value. What a ship *is* is portable; what *this* ship *costs* is
introspected.

## Hypothesis and verification posture

Layer A may legitimately describe a *mechanism* whose exact figures are not yet confirmed on a given
server (e.g. the hypothesized value→content mapping a density-scanner signature implies). Any such
un-introspected number carries a **Verification-status line** marking it a hypothesis, so a reader
never mistakes an unconfirmed figure for a live-confirmed one. The moment a real value is
introspected it lands in Layer B with its own `last_verified_ts` — the authoritative figure is
always the introspected one; a Layer-A hypothesis is a placeholder to be *replaced*, never a value
to *decide on*.

## Per-server keying → world identity

Every row in this store is scoped to exactly one world, by the single shared keying rule: the
identity tuple **host + game-letter + character**. See [world-identity](/engine/world-identity.md)
for the full rule and its rationale — this store is one of its enumerated consumers and invents no
key of its own. The consequence: a ship stat introspected in one galaxy is *structurally* invisible
in another (different character on the same host+game = different world = different directory), so a
value read on one server can never silently drive a decision on a different one.

## Read-only catalog acquisition — VIEW is never BUY

Rows enter this store by *reading a listing*, never by acquiring from it. `tw probe`
(`catalog_cli.py`) is **not** that read path — it is daemon-free, TCP-connect-only catalog hygiene
(liveness sidecar; no telnet, no banner, no game-data rows). In-game rows enter when listing text
is already on screen: opportunistic settle-edge capture (`game_data_capture`, below) parses
shipyard/scanner/TransWarp/item buffers into the rows above. The never-commit crawl contract —
pre-classify keys from menu text, follow only clearly-safe nav/info, and **never press
purchase/sell/attack/deploy/genesis/confirm** — is owned by
[menu-map-and-introspection](/engine/menu-map-and-introspection.md), which populates this store;
this concept is the *destination* of those reads, not the owner of the crawl. Acquiring a scanner or
a TransWarp drive that the store shows as available is a separate, human-approved *behavior*, gated
like any other action — never a side effect of having read the catalog.

## Who reads the store (and the rule that it never reads itself)

The store is a passive fact table with a closed set of readers:

- **Guards** read it to check a taught behavior's preconditions (is this ship commissionable at the
  player's alignment? is a quote even known?).
- The **retrospective, human-invoked AI teacher** reads it when drafting a proposed rule.
- The **coaching engine** and **priority / ship-progression** layers read stat rows to rank
  candidate ships and explain tradeoffs — the *economic use* of these numbers lives there (see
  [priority-engine](/engine/priority-engine.md) and
  [ship-progression](/strategy/ship-progression.md)), not here.
- The **human** reads it directly.

What never happens: the store reading *itself* to select a live keystroke. It informs decisions made
by guards, the human, and the retrospective teacher; it does not make them. The only senders of live
keystrokes anywhere in the trainer remain `{app, human}` — a data store is not among them.

# Examples

**A hold-price decision with no quote.** The upgrade scheduler wants to know whether expanding holds
pays off. It asks the store for the current per-hold price. This world has never had one
introspected, so the store returns *nothing*. The scheduler skips the upgrade branch entirely — it
does **not** fall back to a stock TW2002 figure. No decision is made on an invented number.

**A stat needed for a ship suggestion.** Ship-progression wants to compare a bigger ship's holds
against its turns-per-warp cost. It reads both from the introspected ship row for *this* world. If
the row was never captured on this server, the comparison simply can't be made from authored
data — the portable reference tells the human *that* turns-per-warp matters, but never *what* it is
here.

**A galaxy boundary.** A player introspected a full shipyard on `host / game A / character-one`.
They re-roll a new character, `character-two`, on the same host and game letter. The new world's
game-data store starts empty; none of `character-one`'s ship rows are visible, because the two
characters are two different worlds by the keying rule. The old numbers cannot leak into the new
galaxy where they may be false.

**A hand-edited number is refused.** Someone edits the on-disk store to add a "convenient" ship row
with `source: "authored"`. On the next load the store rejects it — `source` must begin with
`introspected` — so the fabricated value never reaches a consumer.

# Capture-module trust tiers (observed vs derived)

Not every capture module that *can* parse game text is eligible to **persist** into authoritative
store or world-model state. Two trust tiers govern wiring:

| Tier | What it is | Tip examples | Persist? |
|---|---|---|---|
| **Observed live** | Values read directly from a settled live screen into the world model | `density_scan_capture`, `cim_report_capture`, opportunistic `game_data_capture` | **Yes** — observed data, tagged at write time |
| **Derived estimate** | Numbers inferred over fixtures, synthetic rows, or unverified hypotheses | `port_floor_capture` (analysis-only; every result `verified_vs_live=False` today) | **No** — must not write back into canonical hypothesis constants or any persisted field that downstream readers treat as confirmed |

A derived estimate must stay analysis-only until its inputs are genuinely live-verified; writing
it into persisted state would make unverified numbers *look* confirmed (see
`DECISION-PORT-FLOOR-CAPTURE-HOLD-RATIONALE` in [DECISIONS.md](/DECISIONS.md), 2026-08-09).
Future capture modules should classify themselves against this table before wiring a persist path.

# Code divergence

DOCS WIN: the following are places where the current implementation has not yet reached the target
this concept prescribes. The prescription stands; these are recorded, not silently conformed to.

- **The introspector's row grammar is constructed; live capture is partial.** The parser that
  turns a StarDock/shipyard/scanner/TransWarp/item screen into rows (`introspector.py`) matches a
  listing grammar *constructed* from the documented TW2002 shipyard convention plus this project's
  own proven divider style. A historical fixture
  (`tests/fixtures/stardock_shipyard_listing.txt`) and a 2026-08-08 live-drive pass
  ([`stardock-ship-purchase-capture-2026-08-08`](/research/stardock-ship-purchase-capture-2026-08-08.md))
  exist, but they diverge: the live session reached a **read-only** Onboard Computer ship catalog
  (`C`→`C`) yet did **not** reproduce the `-=-=- StarDock Shipyard - Ship Registration -=-=-`
  listing screen or any purchase-confirm prompt on that server. Until the daemon reads a real
  listing matching the parser's grammar on a live server, every introspected ship/equipment row
  remains provisional-by-construction and expects a refinement pass. This is exactly why the
  two-layer gate matters: the store still refuses any *authored* number, but the parser's
  field-mapping is itself unproven against the live listing path still missing ground truth.

- **`tw probe` today is TCP-connect-only; it does not populate game-data rows.** On tip, `tw probe`
  lives in `catalog_cli.py` (`tcp_probe` / `run_catalog_tcp_probe`): one socket connect per catalog
  endpoint, write liveness sidecar — **no telnet negotiation, no banner read, no front-end
  classification**. There is no `probe.py` on tip. It is daemon-free catalog hygiene, not an entry
  rung of in-game introspection, and it does **not** drive catalog screens into this store's
  ship/scanner/TransWarp/item rows. That fill path is `game_data_capture` (below), not `tw probe`.

- **Opportunistic StarDock capture→persist is LIVE on tip.** `game_data_capture.py`
  (`GameDataCapture.tick` → `capture_screen`) parses shipyard / cargo-hold listing text already on
  the settle-edge watch event and persists Layer-B rows via `game_data` — never sends, never crawls.
  Wired from `app.py`'s play-loop idle tick (`gamedata_capture.tick`). Introspector grammar remains
  provisional-by-construction until a broader live-capture corpus refines it; the *trigger* that
  was "the missing link" is no longer missing. PWO-092 Option B (navigate/send
  to reach StarDock catalog screens for an active crawl) stays HELD. Passive
  current-ship `I` parse (PR #471 · `parse_current_ship_info`) is a separate
  no-send path and does not lift that hold.

- **The store's authored numeric layer is deliberately empty.** By design there are *no* stat values
  in the portable reference, and the introspected store on a fresh world is empty until a real
  capture lands. This is the intended state, noted only so it is not mistaken for missing data: the
  absence of numbers is the two-layer rule working, not a gap to be filled by authoring them.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot; the app plays back only
  taught knowledge and stops on the unrecognized; knowledge stores are *read* by guards, the
  retrospective teacher, coaching, and the human, and a store never reads itself to drive.
- Companion portable-semantics reference — `tw2002-ships-and-equipment.md` (Layer A: what a ship and
  each stat axis / device *is* and *means*, carrying no values).
- Internal design history — the per-server game-introspection meta-principle (portable canon vs live
  per-server data, the two-layer split), the ships-and-stats introspection requirement, and the
  density-scanner / TransWarp economic-role notes.
- Code modules — `game_data.py` (the schema, the introspected-only `source` gate on both write and
  load, the per-world persist/query bridge, the singleton cargo-hold quote), `introspector.py` (the
  pure text→rows parser, its no-clock / stamp-at-write-time contract, and its last-header
  stale-scrollback anchoring — the same LAST-match discipline `state_parser.py` uses),
  `game_data_capture.py` (opportunistic settle-edge capture→persist; never-send), and
  `catalog_cli.py` (`tw probe` — TCP-only catalog liveness sidecar; no banner; does not fill rows).
- Cross-cutting invariants — [world-identity](/engine/world-identity.md) (host + game-letter +
  character keying), the read-only never-commit crawl contract owned by
  [menu-map-and-introspection](/engine/menu-map-and-introspection.md), and the economic consumers
  [priority-engine](/engine/priority-engine.md) and [ship-progression](/strategy/ship-progression.md).
