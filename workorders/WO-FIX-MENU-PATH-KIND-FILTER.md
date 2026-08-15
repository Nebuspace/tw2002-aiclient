# WO-FIX-MENU-PATH-KIND-FILTER

**Status:** implement BFS kind filter  
**Branch:** `wo/FIX-MENU-PATH-KIND-FILTER`  
**Seat:** impl-aiclient-h1  
**Depends-on:** WO-FIND-MENU-PATH-KIND-FILTER-SCOUT (DONE — recommended filter-at-BFS)

## Goal

Make `find_menu_path` enforce canon's safe walk set (`nav|info`) structurally, not only via the
emergent action→`<unexplored>` sink.

## Scope

- `tw2002_aiclient/menu/knowledge.py` — filter BFS adjacency to `SAFE_MENU_WALK_KINDS`
- `tests/test_menu_knowledge_edge_kinds.py` — action-to-real-node skip; retired kinds not walked
- `canon/engine/menu-map-and-introspection.md` — Code-divergence CLOSED note
- This workorder file

## Accept

- `find_menu_path` never returns a path containing an `action` (or other non-safe) edge.
- Unexplored-sink assert retained.
- Tests green for the new pins.

## Proof

- `.venv/bin/python -m pytest -n0 tests/test_menu_knowledge_edge_kinds.py tests/test_menu_nav*.py` (and any other find_menu_path consumers) green.
- live-prove `n/a` (offline pathfinding).
