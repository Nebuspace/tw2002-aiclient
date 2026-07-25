# WO-SERVERS-CATALOG-HONESTY

> Status: **BUILT, NOT LANDED** — changes exist in a worktree off `d927e07`;
> nothing committed, nothing pushed. Do not read this file as evidence that
> the corrections are on a tip.
> Base: `d927e07` · UTC: 2026-07-25

## Goal

Docs-only honesty pass: make every count, claim and status stamp in the
servers-catalog documentation match what the tracked files actually contain,
verified **by execution** rather than by restating prior text.

## Method

Every number below was recomputed from the two tracked config files with
`tomllib` / `json` — never copied from an earlier revision. Claims that could
*not* be re-derived from the repo are flagged as such in the docs instead of
being asserted.

## Counts verified (all confirmed correct at `d927e07`)

| Measure | Verified |
|---|---|
| `config/servers.toml` entries / unique `(host.lower(), port)` | 44 / 44 |
| `servers.toml` by `status=` tag | 19 `listed` · 22 `listed_bbsguide` · 3 `archive_seed` |
| `config/servers.inventory.json` rows | 89 |
| Inventory by `status` | 19 · 25 · 3 · 42 `dead` |
| Inventory non-dead rows → unique keys | 47 → 44 (3 dedup aliases) |
| toml key set vs inventory non-dead key set | identical, empty difference both ways |
| MicroBlaster live vs inventory `status=listed` | identical 19-endpoint set |
| BBSGuide source listings | 37 BBSes → 39 inventory rows → 36 unique keys |
| Dual-status endpoints (BBSGuide-listed *and* in graveyard) | exactly 3 |

## Corrected — claims that did not survive checking

1. **`twgs.exiled.org:2002` was documented as absent from the greenfield
   scrape. It is not** — it is in the MicroBlaster graveyard as `eXiled`
   (dead). The inventory note and `WO-SERVERS-CATALOG-SCRAPE.md` both
   asserted the false version. Corrected in place; the resulting policy
   contradiction is recorded, not resolved (see *Left open* below).
2. **Graveyard completeness overstated.** The docs implied the inventory
   records the MicroBlaster graveyard; it records a **42-row subset**. The
   true graveyard size is not reproducible from the repo, so it is described
   qualitatively rather than given a number.
3. **"37 entries" was ambiguous.** True, but it counts *BBS listings*, not
   endpoints. Made explicit (37 listings → 39 rows → 36 unique keys).
4. **Stale counts** in `WO-SERVERS-CATALOG-SCRAPE.md` (41 toml / 86 inventory)
   predate archive merge `a7e66c1`; superseded and marked as such.
5. **Ephemeral evidence not marked.** That WO cites two `/tmp` JSON files as
   Inputs. They are untracked, absent from any clone, and will not survive a
   reboot. Now flagged where cited.
6. **Archive provenance is not clone-verifiable.** `archive/` is gitignored,
   so the `archive_seed` rows cannot be re-derived from the repo. Stated in
   the docs rather than left as an implied citation.

## Left open — deliberately not fixed

- **`twgs.exiled.org:2002` membership.** It is the only `servers.toml` entry
  that is dead on its source with no live/listed backing, contradicting the
  documented Dead-entries policy. Dropping or reclassifying it changes what an
  operator is offered — a curation call, not a docs call. Documented in
  `docs/community-sources.md` section 5 and left to the catalog owner.
- **Personal-name-shaped content in the catalog.** Several tracked entries
  carry operator display names and hostnames that read as real personal names
  (one inventory `name` field is a full personal name; several hostnames embed
  what appear to be surnames). These are public BBS-directory listings and
  predate this pass. They are *not* restated here, to avoid adding further
  instances. Whether the public-repo naming rule should force a scrub is a
  policy question for Max — flagged, unchanged.
- **`KNOWN_NON_ASCII_HELP` contents.** Untouched by design; only the module
  docstring was clarified.

## Non-goals

No re-scrape · no product `.py` change · no `servers.toml` membership change ·
no allowlist change · no secrets surface touched.
