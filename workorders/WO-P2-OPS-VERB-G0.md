# WO-P2-OPS-VERB-G0 — menu_sig / nav / map_view pure modules (no CLI yet)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`d7630b1`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-G-PREP.md` G0 · `canon/engine/menu-map-and-introspection.md`

## Goal
Port read-only `menu_sig` + `menu_nav` + `menu_map_view` (+ thin knowledge-path helper if required) with greenfield unit tests — no CLI verb yet. Modules importable; no fake help verbs. Based on archive menu_* (~230 LOC).

## Scope
- New modules under `tw2002_aiclient/` (non-session package matching tip layout)
- `tests/` — 23 unit tests (greenfield, no `import twclient`)
- README/WO one-liner that substrate landed
- Path-leak

## Constraints
- No `tw menumap` CLI yet (G1)
- No crawler/G2; no loops/autoloop
- No fake help verbs
- Archive reference-only; no `import twclient`

## Accept
1. Modules importable; `menu_sig` + `menu_nav` + `menu_map_view` unit tests green
2. No `menumap` on help (deferred to G1)
3. Path-leak green

## Proof
23 unit tests green + full suite exit 0. Hub Completeness 96 / Quality 95 / Safety 98 / Craft 94 → SHIP.

## Refs
`WO-P2-OPS-VERB-G-PREP.md` G0 · archive menu_* · hub Accept + Push GO @ 15:00:23Z
