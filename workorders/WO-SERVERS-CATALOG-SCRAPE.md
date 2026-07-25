# WO-SERVERS-CATALOG-SCRAPE — EXECUTED

> Status: **DONE** · Seat: `monk` · UTC: 2026-07-25

## Goal
Replace placeholder `config/servers.toml` with a curated public catalog
derived from scraped inventories; write full scrape inventory JSON; document
ClassicTW community forums as future scrape targets.

## Inputs
- `/tmp/bbsguide-parsed.json` — 37 TWGS entries from telnetbbsguide.com
- `/tmp/mb-servers.json` — MicroBlaster live (19) + dead graveyard entries

## Files written
| Path | Description |
|---|---|
| `config/servers.toml` | 41 real public catalog entries; zero placeholders |
| `config/servers.inventory.json` | Full scrape inventory: 44 live/listed + dead graveyard + community forum URLs |
| `docs/community-sources.md` | ClassicTW, BBSGuide, MicroBlaster source notes + catalog policies |
| `docs/OPERATOR.md` | One-line pointer to community-sources.md added |

## Counts
- `servers.toml` entries: **41** (19 MicroBlaster live + 22 BBSGuide-unique)
- Inventory live/listed entries: **44** (including dedup-note-only rows for NoWhere, Star Killer's duplicate, Viper's Pit)
- Inventory dead entries: sourced from MicroBlaster graveyard
- Deduped away: NoWhere TWGS → Joes Tavern; Star Killer's TWGS + Viper's Pit TWGS → Star Killer's Ice9

## Archive merge — 2026-07-25

3 entries from `archive/pre-rebirth-2026-07-23` (WO-MS-1 catalog, snapshot 2026-07-20) added to `servers.toml` (41→44) and `servers.inventory.json` (86→89) as `status=archive_seed`:
- `eclipsebbs.com:2002` — Eclipse BBS — sources=seed,telnetbbsguide
- `polarwireless.ca:2002` — Crawford Intl Online Gaming — sources=classictw
- `twgs.exiled.org:2002` — Alpha Quadrant Invasion — sources=classictw

These were confirmed absent from the 2026-07-25 greenfield scrape (verified of 39-archive dedup check).

## Constraints honored
- No product `.py` modified (app.py `example_one` refs are UI fixture helpers; no tests assert on them)
- No `/Users/` paths in any written file
- No credentials or secrets
