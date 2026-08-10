# WO-CANON-FIX-MENU-MAP-STALE-TWCLIENT-CITATIONS

**Status:** OPEN (building)  
**Priority:** LOW  
**gated:** no · **schema:** n/a (docs only)

## Goal

Remap load-bearing Citations in `canon/engine/menu-map-and-introspection.md` (and residual
`spectate-and-attach.md` [8]/[9]) from archived `twclient/*` paths to tip
`tw2002_aiclient/*` equivalents — residual of DONE `WO-CANON-CLEANUP-STALE-TWCLIENT-CITATIONS`
(PR #431), which only remapped action-safety-guards + session-engine.

## Verify-first (origin/main @ 42dcf41a)

| Citation | Was | Tip truth |
|---|---|---|
| [1] crawler | `twclient/menu_crawler.py` | `tw2002_aiclient/menu/crawler.py` (body already names tip) |
| [2] crawl driver | archive + retired tip note | keep archive/retired honesty (no live module) |
| [3] introspector | `twclient/introspector.py` | `tw2002_aiclient/introspector.py` |
| [4] probe | `twclient/probe.py` (L0/L1 peek) | tip split: `session/iac.py` + `catalog_cli.py` (`tw probe` TCP) — not a silent rename |
| [5] nav/knowledge/map | `twclient/menu_*` | `menu/nav.py` · `menu/knowledge.py` · `menu/map_view.py` |
| [6] sig | `twclient/menu_sig.py` | `menu/sig.py` |
| [7] ship upgrade | `twclient/ship_upgrade_decision.py` | `ship_upgrade_decision.py` |
| [8] world_id | `twclient/world_identity.py` | `world_identity.py` |
| spectate [8]/[9] | bare `twclient/terminal.py` / `spectate_app.py` | tip `session/terminal.py` + archive-only spectate_app |

Directed READY backlog tip-sweep: 2026-08-09 audit READY rows are tip-closed ghosts (FRAMES
#642/#645, TEST-CATALOG #644, TRADE-DRIVER #646, hub tip-true batches, etc.) — this residual is
the next real docs-honesty gap.

## Scope

- `canon/engine/menu-map-and-introspection.md` (Citations)
- `canon/surfaces/spectate-and-attach.md` (Citations [8]–[9] only)
- `workorders/WO-CANON-FIX-MENU-MAP-STALE-TWCLIENT-CITATIONS.md` (this file)

## Accept

1. No bare `twclient/` path in menu-map Citations [1], [3]–[8] unless labeled archive/retired.
2. Citation [4] does **not** claim tip `tw probe` is archive L0 banner classification.
3. Spectate [8] cites tip `session/terminal.py`; [9] labeled archive / do-not-cite-as-tip.
4. Docs-only; path-leak clean.

## Proof

`git grep -n 'twclient/' canon/engine/menu-map-and-introspection.md` shows only archive/retired
labels; spectate [8]/[9] remapped; live-prove n/a (canon honesty).
