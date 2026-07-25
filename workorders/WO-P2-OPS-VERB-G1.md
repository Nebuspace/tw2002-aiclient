# WO-P2-OPS-VERB-G1 — tw menumap CLI (read-only inspector over G0 menu store)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`cbfb1e5`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` G1 · `WO-P2-OPS-VERB-G-PREP.md` G1 · `canon/engine/menu-map-and-introspection.md`

## Goal
Wire read-only `tw menumap` over G0 (`menu_map_view` + knowledge) — store inspect + optional live localize via `tw screen` / status. No crawler write. `--profile` cut honest.

## Scope
- `tw2002_aiclient/session/cli.py` (`tw menumap` sub-command)
- Thin glue to G0 modules
- Rehab `tests/test_cli_menumap.py` (greenfield)
- `_SHIPPED_VERBS` allowlist + README/WO
- Path-leak

## Constraints
- No G2 crawler; no loops/autoloop; no spectate; no chrome
- Read-only (no game drive; `screen` localize only, never sends)
- `--profile` deferred or cut honest
- Full suite green

## Accept
1. `menumap` on `./tw --help`
2. FakeSession/store proof (read-only inspect)
3. Allowlist + README updated; `--profile` honest
4. Full suite green

## Proof
7 targeted tests + allowlist green + full suite exit 0. Hub Completeness 95 / Quality 94 / Safety 96 / Craft 93 → SHIP.

## Refs
`WO-P2-OPS-VERB-G-PREP.md` G1 · archive `cmd_menumap` · hub Accept + Push GO @ 15:10:55Z
