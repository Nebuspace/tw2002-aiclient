# WO-HUD-CARGO-BREAKDOWN

**Status:** READY · EXECUTE · HIGH · Max ask 2026-08-01 · Cursor  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/HUD-CARGO-BREAKDOWN`  
**Depends:** `main` ≥ `245dfe3`  
**Plan:** `.samantha/plans/trade-loop-cargo-hud.md` wave 1

## Why

Right HUD paints `CARGO 50` from **empty holds only**. Operators read that as “50 cargo aboard.” Ship-info already prints `Total Holds : N - Empty=M`; `hud_tracking._SHIP_INFO_EMPTY_RE` **captures N then discards it**.

## Goal

Make the CARGO cell explain holds: **empty and total** (and implied filled = total − empty). Do **not** invent per-commodity names in this WO (wave 2).

## Scope

1. **Parse:** Extend cargo read/snapshot to sticky `empty` + `total` when ship-info line present. Port-commerce sentence still supplies empty only (total may stay unknown / sticky from prior `I`).
2. **HUD:** Paint an operator-honest string, e.g. `50 empty / 60` or `empty 50 · filled 10` when total known; if total unknown keep empty with a cue it is empty-holds (not “stuff”). Prefer one HUD cell value (existing `hud.cargo` / compose path) — multi-line only if the right gutter already supports it without layout thrash.
3. **Pins:** ship-info total+empty; port empty-only; display pin; no inference from port *market* commodity rows.
4. **Canon:** Stage DECISION `PENDING-HUD-CARGO-BREAKDOWN` in `canon/DECISIONS.md` OPEN + amend `canon/surfaces/trainer-cockpit.md` cargo blurb to match (empty/total; holdings deferred to wave 2). Public-repo safe.
5. This WO on the branch.

## Out of scope

Per-commodity Ore/Org/Equ (→ **WO-HUD-CARGO-HOLDINGS**) · trade hop LOGS (→ **WO-TRADE-LOOP-HOP-VISIBLE**) · haggle · #283.

## Accept

1. After `I` seed / ship-info observe, HUD CARGO shows empty **and** total (or equivalent honest breakdown), not a bare integer that reads as “contents.”
2. Port-only empty updates still work; never invent total from port market rows.
3. Focused hud_tracking / hud / seed pins green; full suite green.
4. Live-prove **n/a** (display + parse; no money-path start).

## Proof

pytest + STATUS. No self-merge.

## Refs

`session/hud_tracking.py` `_SHIP_INFO_EMPTY_RE` · `cockpit/hud.py` CARGO · `canon/surfaces/trainer-cockpit.md` § Cargo · Max 2026-08-01
