# WO-WIRE-SHIP-CATALOG-ALIGNMENT-RANK-LIVE

**Status:** IN FLIGHT · Cursor · `wo/WIRE-SHIP-CATALOG-ALIGNMENT-RANK-LIVE`
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ `7b15a7e` (upgrade catalog wire #526)
**Refs:** queue-aiclient.md · Gate #1 alignment_rank ·
`ship_upgrade_decision.upgrade_catalog_from_ships` ·
`canon/strategy/ship-progression.md` § Alignment / rank gate

## Why

Gate #1 (alignment/rank) was structurally disabled on the live path:
`upgrade_catalog_from_ships` called `ship_row_to_spec` without
`commissioned=` (always defaults True), and player standing was never
parsed from I-info (`Alignment=N` on Rank/Exp) into status. The correct
comparison path in `ship_spec_from_current_info` stayed unused.

## Goal

Make catalog `commissioned` reflect live trader alignment when I-info has
been observed, so `choose_upgrade` can refuse uncommissioned hulls with
`alignment_rank`.

## Scope

1. Parse `Alignment=N` (signed) from I-info into `parse_current_ship_info`
   → `alignment`.
2. Emit `current_ship.alignment` + top-level `status["alignment"]` from
   protocol when known (omit-until-known).
3. `upgrade_catalog_from_ships(..., player_alignment=)` sets `commissioned`
   via the shared helper; `merge_upgrade_status_inputs` / 
   `upgrade_player_from_status` plumb standing from status.
4. Pins for fixture parse, catalog commissioned when alignment known, and
   merge path. Recommend-only — no purchase send.

## Out of scope

- Rank-string ordering (still free-form; no comparable rank canon).
- Fail-closed-when-alignment-unknown for every gated hull (would HOLD
  upgrades before first I-info; omit-until-known preserved).
- Money-path / StarDock purchase driver.

## Constraints

- No new deps · explicit-path commits · no path leaks · lead seat.
- Never invent alignment from a screen that does not show it.

## Accept

1. Live ship-info fixture yields `alignment == 2`.
2. With `player_alignment` below a catalog `alignment_requirement`, that
   row's `commissioned` is False on the upgrade catalog.
3. `merge_upgrade_status_inputs` with status alignment gates the catalog.
4. Focused pytest green; live-prove **n/a** (recommend-only / parse wire).

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_introspector.py \
  tests/test_ship_upgrade_decision.py \
  tests/test_upgrade_status_wire.py \
  -q -n0 -k 'alignment or upgrade_catalog or parse_current_ship or merge_with'
```

live-prove: `n/a` — offline parse + status merge; no TWGS arm / login path.
