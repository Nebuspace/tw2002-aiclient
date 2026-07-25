# TW2002 Community Sources

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
  with host, port, game count, and last-seen date.
- **Graveyard** — `type=dead` query and individual `ServerDetail` pages record
  servers that were once registered but are no longer responding.  Useful for
  historical research and dedup cross-referencing.

Used as the primary live-server source for `config/servers.toml`.  Display
names from this source are preferred when both MicroBlaster and BBSGuide list
the same `(host.lower(), port)` endpoint.

### Telnet BBS Guide — TWGS Software Category
<https://www.telnetbbsguide.com/bbs/software/twgs/>

A BBS listing site with a TWGS-tagged category.  37 entries scraped
2026-07-25.  Per-entry detail pages carry individual source URLs
(e.g. `https://www.telnetbbsguide.com/bbs/<slug>/`).

Used as a supplemental source — entries not already in the MicroBlaster live
listing are included in the catalog with `status=listed_bbsguide`.

---

## 3. Catalog Policies

| Policy | Detail |
|---|---|
| **Telnet default port** | Port 23 is applied when a source page omits the port.  All other ports are explicit. |
| **Dedup key** | `(host.lower(), port)` — the same endpoint under different capitalisation is one entry. |
| **Name preference** | MicroBlaster display name wins on a dedup collision. |
| **Dead entries** | Recorded in `config/servers.inventory.json` for research; **not** baked into `config/servers.toml` unless also on a live/listed source. |
| **Liveness** | The catalog is a **curated snapshot**, not a liveness probe.  Entries go stale.  Treat it as a starting-point address book. |
| **No credentials** | Neither `servers.toml` nor `servers.inventory.json` contains passwords, API keys, or any secret. |
| **Scrape date** | 2026-07-25 UTC.  Re-scrape MicroBlaster and BBSGuide periodically to refresh stale entries. |
| **Archive merge (2026-07-25)** | 3 entries from `archive/pre-rebirth-2026-07-23` catalog (WO-MS-1, snapshot 2026-07-20) merged into `servers.toml` and `servers.inventory.json` as `status=archive_seed`.  These were present in the pre-rebirth inventory but absent from the 2026-07-25 greenfield scrape: `eclipsebbs.com:2002` (seed/telnetbbsguide), `polarwireless.ca:2002` (classictw — Crawford Intl Online Gaming), `twgs.exiled.org:2002` (classictw — Alpha Quadrant Invasion). |
