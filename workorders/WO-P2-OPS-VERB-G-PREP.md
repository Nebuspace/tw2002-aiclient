# WO-P2-OPS-VERB-G-PREP — Menumap / loops inventory (no wire)

> Status: **DONE** · origin `d70520b` (hub Accept stamp 2026-07-26 · PREP docs tip; `582c210` was attach redaction not this PREP)
> Seat: `impl-aiclient-cursor`
> Parent: `WO-P2-OPS-VERB-SURFACE.md` slice G
> HOLD: ops `tw spectate` **RETIRED / WONTBUILD** (Max `@ 13:13:55Z`) · **G2 EXECUTING** · G3→G4 staged (Max GO `@ 13:15:00Z`)

## Goal

Honesty-gated execute plan for remaining slice-G ops verbs (`menumap`, and
related `loops` / `autoloop` / record·mine dependencies). **Do not wire.**

## Tip vs archive (2026-07-24)

| Piece | Tip | Archive |
|-------|-----|---------|
| `tw menumap` CLI | **LANDED** (`cmd_menumap` — store inspect + optional live `screen` localize) | `cmd_menumap` — read-only inspector over knowledge store + optional live `screen` localize |
| `menu_map_view.py` | **LANDED** (`tw2002_aiclient.menu.map_view`, G0) | ~131 LOC pure format/summary |
| `menu_nav.py` / `menu_sig.py` | **LANDED** (`tw2002_aiclient.menu.nav` / `.sig`, G0) | ~76 + ~27 LOC |
| `menu_crawler.py` | **MISSING** | ~944 LOC crawl engine (writes knowledge; not the CLI itself) |
| `tw loops` / `tw autoloop` | **MISSING** | CLI + `loop_player.py` ~369 LOC (needs control_lock + WatchHub — both live) |
| `tw record` / `tw mine` | **MISSING** | skill capture / miner — feeds loops |
| Banked ignored tests | `test_menu_crawler` still `--ignore`; `test_cli_menumap` **un-ignored** (G1) | ~1.6k LOC tests |

**Live tip already usable by a future menumap:** `tw screen` / `tw status` /
WatchHub / control_lock · G0 menu modules under `tw2002_aiclient.menu`.
**G1 LANDED:** `tw menumap` CLI. **G2 EXECUTING** (menu crawler). **Still staged:** loops (G3+) · autoloop (G4).

## Recommended execute slices

| Slice | Goal | Bound | Depends |
|-------|------|-------|---------|
| **G0** | Port `menu_sig` + `menu_nav` + `menu_map_view` (pure, read-only) + rehab unit tests — **LANDED** | Small–medium (~230 LOC + tests) | knowledge path helper (thin) |
| **G1** | Wire `tw menumap` CLI (store-only + optional live localize via `screen`) · un-ignore `test_cli_menumap` — **LANDED** | Small | G0 |
| **G2** | Port `menu_crawler` (writes map) — **EXECUTING** (Max GO `@ 13:15:00Z`; canon K3 legs) | Large (~944 LOC) | G0 · settle/do |
| **G3** | `tw loops` list (protocol + CLI) — needs skill/loop store | Medium | record/mine or empty-honest |
| **G4** | `tw autoloop` + `loop_player` — App drive; control_lock + WatchHub live | Large (~369+ LOC) | G3 · careful vs Max pace-down chrome |

**Honesty bar:** keep `loops` / `autoloop` off `./tw --help` until
the matching slice Accepts. Prefer **G0→G1** (read-only inspector) before
crawler/autoloop.

## Out of scope (this PREP)

Implementing G3/G4 ahead of G2 Accept · inventing ops `tw spectate` (RETIRED) · inventing empty stores.

## Accept (this PREP)

STATUS cites gaps + slices · README/WO honesty · help unchanged · SHA if docs commit.
