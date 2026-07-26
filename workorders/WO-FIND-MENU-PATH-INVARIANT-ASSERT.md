# WO-FIND-MENU-PATH-INVARIANT-ASSERT

**Status:** DONE · origin `f61e10b` (assert + pin)  
**Posted:** 2026-07-26T06:24Z

## Goal

Cheapest interim after scout: one-line assert at `find_menu_path` naming the safe-kinds-only invariant (BFS has no kind filter today; safety is emergent).

## Scope

- `menu/knowledge.py` (or current `find_menu_path` home) + one pin test
- No full BFS kind-filter design (separate router WO)

## Constraints

- Assert names the invariant; does not invent the full filter design
- Scout finding stands: becomes live if crawler presses recorded-not-pressed / second writer

## Accept

Assert + red-then-green pin; suite green.

## Proof

STATUS + SHA · targeted pytest.

## Refs

`WO-FIND-MENU-PATH-KIND-FILTER-SCOUT` DONE · CC scout 01:43Z
