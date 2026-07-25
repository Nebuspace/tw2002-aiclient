# WO-SERVERS-CATALOG-SCRAPE — EXECUTED

> Status: **DONE** · Seat: `monk` · UTC: 2026-07-25

## Goal
Replace placeholder `config/servers.toml` with a curated public catalog
derived from scraped inventories; write full scrape inventory JSON; document
ClassicTW community forums as future scrape targets.

## Inputs
> ⚠️ **Ephemeral evidence.** Both inputs are untracked temp files, not repo
> artifacts. They happened to still exist when this WO was re-verified on
> 2026-07-25, but they will not survive a reboot and are absent from any
> clone. Counts derived *only* from them are flagged as such below.

- `/tmp/bbsguide-parsed.json` — **37 BBS listings** from telnetbbsguide.com
  (37 *BBSes*, not endpoints: they carry 39 endpoint mentions / 38 unique)
- `/tmp/mb-servers.json` — MicroBlaster live (19) + dead graveyard

## Files written
| Path | Description |
|---|---|
| `config/servers.toml` | **44** real public catalog entries; zero placeholders |
| `config/servers.inventory.json` | Scrape inventory: **89** rows (47 non-dead + 42 dead) + community forum URLs |
| `canon/doctrine/server-catalog-sources.md` | ClassicTW, BBSGuide, MicroBlaster source notes + catalog policies + verified-count snapshot |

## Counts (re-counted from the tracked files at `d927e07`)
- `servers.toml` entries: **44** unique `(host.lower(), port)`, no duplicate keys
  — **19** `listed` + **22** `listed_bbsguide` + **3** `archive_seed`
- Inventory rows: **89** = **19** `listed` + **25** `listed_bbsguide` +
  **3** `archive_seed` + **42** `dead`
- Inventory non-dead rows: **47**, collapsing to **44** unique keys — the
  *same set* as `servers.toml` (difference empty both directions)
- The 3 surplus non-dead rows are dedup aliases:
  NoWhere TWGS → Joes Tavern; Star Killer's TWGS + Viper's Pit TWGS → Star Killer's Ice9
- Inventory `dead` rows are a **42-row subset** of the MicroBlaster graveyard,
  not a mirror of it. The full graveyard size is not reproducible from the
  repo (see *Inputs* warning) and is therefore not asserted here.
- Earlier revisions of this WO claimed **41** toml entries and an 86-row
  inventory; both predate the archive merge `a7e66c1` and are superseded.

## Archive merge — 2026-07-25

3 entries from `archive/pre-rebirth-2026-07-23` (WO-MS-1 catalog, snapshot 2026-07-20) added to `servers.toml` (41→44) and `servers.inventory.json` (86→89) as `status=archive_seed`:
- `eclipsebbs.com:2002` — Eclipse BBS — sources=seed,telnetbbsguide
- `polarwireless.ca:2002` — Crawford Intl Online Gaming — sources=classictw
- `twgs.exiled.org:2002` — Alpha Quadrant Invasion — sources=classictw

The archived catalog held **39** entries; all 39 were checked against the union
of the two scrape inputs (192 unique endpoints).

**Correction (2026-07-25, WO-SERVERS-CATALOG-HONESTY).** The original claim
here — that all three were "confirmed absent from the 2026-07-25 greenfield
scrape" — is **false for one of the three**:

| Endpoint | Absent from greenfield scrape? |
|---|---|
| `eclipsebbs.com:2002` | yes |
| `polarwireless.ca:2002` | yes |
| `twgs.exiled.org:2002` | **no** — present in the MicroBlaster graveyard as `eXiled` (dead) |

`twgs.exiled.org:2002` is consequently the only `servers.toml` entry that is
dead on its source and backed by no live/listed source, which contradicts the
documented Dead-entries policy. Its inventory note has been corrected; the
membership question is left open as a curation call.
See `canon/doctrine/server-catalog-sources.md` section 5.

## Constraints honored
- No product `.py` modified (app.py `example_one` refs are UI fixture helpers; no tests assert on them)
- No `/Users/` paths in any written file
- No credentials or secrets
