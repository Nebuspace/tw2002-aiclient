# WO-WM-LANDMARKS-WRITE — populate landmarks from Ports line

**Status:** DONE · origin `b4b92f8` (#165) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28T14:06Z · hub (CC 14:04:20Z evidence)  
**Amended:** 2026-07-28T15:19Z · CC PROCESS-NOTE constraints
**Re-scoped:** 2026-07-28T15:29Z · hub ruling — **P1 only** (see Scope split)

## Goal

Teach `_ingest_settled_sector` / `sector_explore` writer to record `landmarks[]` from the settled screen’s `Ports :` line (e.g. StarDock). Today the screen carries StarDock but WM records `landmarks=[]`, so `find_landmark_sectors` never returns — starves GOALS stardock fields and stale `explore.py` caller claims.

## Constraints (load-bearing)

1. **OMIT `landmarks` when nothing was observed. Never write `[]`.** Upsert is field-replacing; unconditional `[]` erases a known StarDock on the next plain visit. Mirror `warps`/`port` tri-state in `_ingest_settled_sector` (and `world-model.md`: plain visit never clears landmarks).
2. **Canon tokens only:** `stardock`, `class_zero`, `own_planet`, `ferrengi` (lowercase snake). Spacing/underscores matter; `"Class Zero"` ≠ `class_zero`.
3. **Reuse existing `Ports :` parse** — `read_port_from_sector_status` already yields observed=True for StarDock lines; do **not** add a second row parser (`world-model.md` forbids).

## Scope split (hub ruling 15:29Z, after CC evidence 15:27Z)

The original single-part scope is not buildable: **a landmark is a per-sector record, and no
StarDock screen we have carries a sector.** All four captured StarDock fixtures show
`Command [TL=00751:0/0/0/850] (?=Help)? :` with **no `[sector]` bracket** (positive control: ordinary
docked-port fixtures DO carry one), the captured `<StarDock> Where to?` prompt reads
`outcome='absent'` through `read_current_sector` and `unrecognized_screen` through `_gate_screen`,
and no last-known-sector memory exists anywhere in `session/`.

- **P1 — THIS WO.** The write path only. No producer that claims a sector identity it does not have.
- **P2 — `WO-LAST-KNOWN-SECTOR`** (hub-banked). Daemon-side last-known-sector, so a sector-less but
  positively-identified screen can be attributed. Unblocks every StarDock class `classify.py`
  already recognises.
- **P3 — Ports-name extractor.** Banked until a live capture of that line shape exists. Do not
  invent the flyby string as a green oracle.

## Accept (P1)

- `landmarks` **unions** on upsert — no record can shrink a sector's landmark set, so "a plain visit
  never clears them" is structural rather than remembered.
- Dedup is casefold (matching `find_landmark_sectors`); existing order stable, new tokens append.
- Other fields still **replace** (a union leaking into `warps` would accumulate hops that do not exist).
- `write_from_state` still **refuses** `landmarks` — the refusal is deliberate and is not widened.
- `canon/engine/world-model.md` states the asymmetry and why (silence is not a denial).
- Falsification: reverting the union to a plain assignment must turn the pins red.

## Proof

- pytest; live-prove `n/a`

## Refs

- CC 14:04:20Z · 15:17:16Z PROCESS-NOTE · `WO-GOALS-STATUS-VOCABULARY` follow-on
