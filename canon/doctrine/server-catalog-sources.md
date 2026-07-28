---
type: Doctrine
title: Server Catalog Sources
description: Public TWGS directory sources, catalog honesty policies, and verified counts for config/servers.toml and servers.inventory.json — no secrets.
tags: [doctrine, servers, catalog, community, honesty]
timestamp: 2026-07-25T21:10:00Z
---

Public provenance for the operator-facing server address book (`config/servers.toml`) and the
research inventory (`config/servers.inventory.json`). Nothing here is secret or credentials-bearing.
Catalog *membership* curation decisions (e.g. whether a dead archive_seed stays offered) are
operator/product calls — this concept records signals and policy, not a liveness probe.

Reference guide to the public sources used (and planned) for the server catalog
and future prompt/menu pattern research.  Nothing in this file is secret or
credentials-bearing — these are links anyone can open.

---

## 1. ClassicTW.com — Community Documentation Hub

**[ClassicTW.com](https://www.classictw.com/)** is the primary surviving
community hub for TradeWars 2002.  It hosts forums, a wiki, and archives of
player-generated documentation that pre-date TWGS by decades.

### Forum f=7 — Manual / Docs
<https://www.classictw.com/viewforum.php?f=7>

The main reference forum.  Contains:

- **Glossaries** — sector types, commodities, NPC factions, game abbreviations
- **Newbie guides** — first-session walkthroughs, economic primers
- **Wiki pointers** — links to the (now-partially-archived) TW2002 wiki
- **Command references** — prompt-by-prompt breakdowns of the game's menu tree

**Future use:** high-value corpus for prompt/classification pattern mining.
When the AI client needs to recognise a new game state or menu, this forum
is the first place to look for documented human-readable descriptions.
*Not scraped in the initial server-catalog pass — document-only for now.*

### Forum f=15 — Helpers & Scripts
<https://www.classictw.com/viewforum.php?f=15>

Community-shared automation: trainers, helper programs, external scripts, and
macro collections.

**Future use:** pattern-mining for known prompts and menu sequences that
community scripts already handle.  Useful for cross-referencing the AI
client's parser against what human authors already reverse-engineered.
*Not a code-import source — review for patterns only.*

> **Policy note on `sid=`:** phpBB appends a session id (`sid=…`) to forum
> URLs when you are logged in.  Strip it from any durable link (the paths
> above are already clean).

---

## 2. Address Inventory Sources

### MicroBlaster.net — TWGS Server Directory
<http://www.microblaster.net/Servers.aspx>

The longest-running TWGS server directory.  Provides:

- **Live listing** — `Servers.aspx` enumerates currently-registered servers
  with host, port, game count, and last-seen date.  All **19** entries from
  this listing are in the catalog as `status=listed`.
- **Graveyard** — `type=dead` query and individual `ServerDetail` pages record
  servers that were once registered but are no longer responding.  Useful for
  historical research and dedup cross-referencing.  **The inventory carries a
  42-row *sample* of the graveyard, not a mirror of it** — the full graveyard
  is substantially larger.  Its exact size is *not* reproducible from this
  repo: the scrape landed in an untracked temp file, so treat the 42 `dead`
  rows as "the ones we had reason to keep", never as "the complete graveyard".

Used as the primary live-server source for `config/servers.toml`.  Display
names from this source are preferred when both MicroBlaster and BBSGuide list
the same `(host.lower(), port)` endpoint.

### Telnet BBS Guide — TWGS Software Category
<https://www.telnetbbsguide.com/bbs/software/twgs/>

A BBS listing site with a TWGS-tagged category.  **37 BBS listings** scraped
2026-07-25 — that count is *BBSes*, not endpoints: a listing may publish more
than one `(host, port)`.  Those 37 listings contribute **39 rows** to
`config/servers.inventory.json`, covering **36 unique** `(host, port)` keys
after dedup.  Per-entry detail pages carry individual source URLs
(e.g. `https://www.telnetbbsguide.com/bbs/<slug>/`).

Used as a supplemental source — entries not already in the MicroBlaster live
listing are included in the catalog with `status=listed_bbsguide`.

---

## 3. Catalog snapshot — verified counts

Every number below was **counted from the two tracked files**, not carried
forward from an earlier draft.  Measured at commit `d927e07`; both config
files are untouched by every commit from `a7e66c1` (the archive-merge commit)
through `d927e07`, so the snapshot holds across that whole range.  The pass
that wrote this section corrected one inventory `notes` string (section 5) and
changed **no count and no membership**.  Re-derive any row with `tomllib` /
`json` over the tracked files — if a number here ever disagrees with the
files, **the files are right and this table is stale**.

| Measure | Count |
|---|---|
| `config/servers.toml` entries | **44** |
| — unique `(host.lower(), port)` | **44** (no duplicate keys) |
| — by `status=` tag in `description` | **19** `listed` · **22** `listed_bbsguide` · **3** `archive_seed` |
| `config/servers.inventory.json` rows | **89** |
| — by `status` field | **19** `listed` · **25** `listed_bbsguide` · **3** `archive_seed` · **42** `dead` |
| — non-`dead` rows | **47** |
| — unique non-`dead` `(host.lower(), port)` | **44** |

The 44 unique non-`dead` inventory keys and the 44 `servers.toml` keys are the
**same set** — the difference is empty in both directions.  The 3 surplus
non-`dead` *rows* are the dedup aliases below, which are recorded in the
inventory for traceability and are never separate `servers.toml` entries:

| BBSGuide listing | Deduped into (MicroBlaster name wins) |
|---|---|
| NoWhere TWGS | Joes Tavern |
| Star Killer's TWGS | Star Killer's Ice9 |
| Viper's Pit TWGS | Star Killer's Ice9 |

## 4. Catalog Policies

| Policy | Detail |
|---|---|
| **Telnet default port** | Port 23 is applied when a source page omits the port.  All other ports are explicit. |
| **Dedup key** | `(host.lower(), port)` — the same endpoint under different capitalisation is one entry. |
| **Name preference** | MicroBlaster display name wins on a dedup collision. |
| **Dead entries** | Recorded in `config/servers.inventory.json` for research; **not** baked into `config/servers.toml` unless also on a live/listed source.  **One entry currently breaks this rule** — see *Known exception* below. |
| **Dual-status endpoints** | Three endpoints are listed as active on BBSGuide *and* appear in the MicroBlaster graveyard: `twgs.geekm0nkey.com:23`, `game.tw2002.net:23`, `thequesttwgs.game-host.org:23`.  `servers.toml` keeps the BBSGuide-listed row; the inventory retains **both** rows so the conflict stays visible.  This records conflicting directory signals — it is **not** a liveness claim either way. |
| **Liveness** | **Split from provenance (WO-CATALOG-SOURCE-LIVENESS-SPLIT).** Inventory/toml `status` / `status=` tags are **listing provenance** (`listed` / `listed_bbsguide` / `archive_seed` / `dead` graveyard sample) — never TCP reachability. Measured reachability is optional `liveness` + `last_probed_utc` on a row and/or `config/servers.liveness.json` from `scripts/catalog-tcp-probe.py` (TCP connect only; no login/turns). Summaries use `tw2002_aiclient.server_inventory.summarize_inventory` — there is **no** `connectable` rollup from provenance (that false `connectable: 0` reading is banned). Live-prove sizing uses `planning_endpoints` (directory-active rows), which stay available even when liveness is `unprobed` or `unreachable`. |
| **No credentials** | Neither `servers.toml` nor `servers.inventory.json` contains passwords, API keys, or any secret. |
| **Scrape date** | 2026-07-25 UTC.  Re-scrape MicroBlaster and BBSGuide periodically to refresh stale entries. |
| **Archive merge (2026-07-25)** | 3 entries from the `archive/pre-rebirth-2026-07-23` catalog (WO-MS-1) merged into `servers.toml` and `servers.inventory.json` as `status=archive_seed`: `eclipsebbs.com:2002` (seed/telnetbbsguide), `polarwireless.ca:2002` (classictw), `twgs.exiled.org:2002` (classictw).  **Two** of the three — `eclipsebbs.com:2002` and `polarwireless.ca:2002` — are genuinely absent from the 2026-07-25 greenfield scrape.  The third is not; see *Known exception* below. |
| **Archive provenance is not clone-verifiable** | `archive/` is **gitignored** (see `.gitignore`), so the pre-rebirth catalog this merge cites is absent from a fresh clone.  A reader cannot re-derive the `archive_seed` rows from the repo alone — they rest on a local-only tree.  Stated here rather than left as an implied citation. |

---

## 5. Known exception — `twgs.exiled.org:2002`

Recorded rather than quietly corrected, because resolving it is a **curation
decision**, not a documentation one.

`twgs.exiled.org:2002` carries `status=archive_seed` in both `servers.toml` and
the inventory, and until this pass its inventory note read *"absent from
2026-07-25 greenfield scrape"*.  **That was wrong.**  The endpoint *is* in the
greenfield scrape — in the MicroBlaster **graveyard**, listed as dead under the
name `eXiled`.  The note has been corrected to say so.

Two consequences, both left open:

1. **It contradicts the Dead-entries policy.**  That policy says a dead entry
   is not baked into `servers.toml` unless it is *also* on a live/listed
   source.  This endpoint is on no live/listed source — it is dead on
   MicroBlaster and absent from BBSGuide — yet it sits in `servers.toml`.  It
   is the only entry in the catalog that does this.
2. **The fix is a judgement call.**  Dropping it from `servers.toml`, or
   reclassifying it `dead`, changes what an operator is offered in the address
   book.  This pass deliberately did **not** make that call: the note now
   states the truth, and the membership question is left to whoever owns
   catalog curation.

Note the asymmetry with the *Dual-status endpoints* policy row: those three
endpoints stay in `servers.toml` because a live source (BBSGuide) still lists
them.  This one has no such backing.
