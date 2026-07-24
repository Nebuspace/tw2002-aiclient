# WO-P2-OPS-VERB-G-PREP — Menumap / loops inventory (no wire)

> Status: **DONE** pending Accept · tip `582c210`
> Seat: `impl-aiclient-cursor`
> Parent: `WO-P2-OPS-VERB-SURFACE.md` slice G
> HOLD: F2 spectate parked (hub @ 14:46:58Z) until Max re-opens CC·Fable

## Goal

Honesty-gated execute plan for remaining slice-G ops verbs (`menumap`, and
related `loops` / `autoloop` / record·mine dependencies). **Do not wire.**

## Tip vs archive (2026-07-24)

| Piece | Tip | Archive |
|-------|-----|---------|
| `tw menumap` CLI | **MISSING** | `cmd_menumap` — read-only inspector over knowledge store + optional live `screen` localize |
| `menu_map_view.py` | **MISSING** | ~131 LOC pure format/summary |
| `menu_nav.py` / `menu_sig.py` | **MISSING** | ~76 + ~27 LOC |
| `menu_crawler.py` | **MISSING** | ~944 LOC crawl engine (writes knowledge; not the CLI itself) |
| `tw loops` / `tw autoloop` | **MISSING** | CLI + `loop_player.py` ~369 LOC (needs control_lock + WatchHub — both live) |
| `tw record` / `tw mine` | **MISSING** | skill capture / miner — feeds loops |
| Banked ignored tests | `test_cli_menumap` · `test_menu_*` still `--ignore` (`twclient`) | ~1.6k LOC tests |

**Live tip already usable by a future menumap:** `tw screen` / `tw status` /
WatchHub / control_lock. **Missing substrate:** `game_knowledge` store path +
menu_* modules (not under `session/` today).

## Recommended execute slices

| Slice | Goal | Bound | Depends |
|-------|------|-------|---------|
| **G0** | Port `menu_sig` + `menu_nav` + `menu_map_view` (pure, read-only) + rehab unit tests | Small–medium (~230 LOC + tests) | knowledge path helper (thin) |
| **G1** | Wire `tw menumap` CLI (store-only + optional live localize via `screen`) · un-ignore `test_cli_menumap` | Small | G0 |
| **G2** | Port `menu_crawler` (writes map) — separate from inspector; may need ensure/drive | Large (~944 LOC) | G0 · settle/do |
| **G3** | `tw loops` list (protocol + CLI) — needs skill/loop store | Medium | record/mine or empty-honest |
| **G4** | `tw autoloop` + `loop_player` — App drive; control_lock + WatchHub live | Large (~369+ LOC) | G3 · careful vs Max pace-down chrome |

**Honesty bar:** keep `menumap` / `loops` / `autoloop` off `./tw --help` until
the matching slice Accepts. Prefer **G0→G1** (read-only inspector) before
crawler/autoloop.

## Out of scope (this PREP)

Implementing G0–G4 · spectate F2 (HOLD) · chrome/cockpit · inventing empty stores.

## Accept (this PREP)

STATUS cites gaps + slices · README/WO honesty · help unchanged · SHA if docs commit.
