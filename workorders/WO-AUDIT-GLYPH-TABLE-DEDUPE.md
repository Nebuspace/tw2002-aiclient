# WO-AUDIT-GLYPH-TABLE-DEDUPE — Import thin glyphs from draw.py

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`8facad9`** (CC · Fable 5) · docs stamp Cursor  
> Type: polish · Priority: P2 · Lens: L4  
> Refs: `screens.py` glyph tables · `cockpit/draw.py` THIN_* · `tests/test_glyph_table_dedupe.py`

## Tip verdict
**DONE** on origin `8facad9` — screens glyph tables are import-and-extend from draw `THIN_*` (+ `sel`); key-set pin prevents silent re-divergence. Selectors **not** unified (tables-only). Render unchanged (zero fixture updates). Proof: `tests/test_glyph_table_dedupe.py` 10/10 · suite green. Banked follow-on: stale `screens._unicode_ok` locale docstring → `WO-AUDIT-UNICODE-OK-DOCSTRING`.

## Goal
Stop byte-duplicating thin glyph tables in `screens.py`; import + extend from `draw.py` (+ `sel` key if needed).

## Scope
- A: `screens.py` — import tables
- B: `cockpit/draw.py` — single source
- C: grep proof no duplicate constants

## Constraints
Docs/visual parity only; no seat-key changes. Tables-only — do not silently unify `unicode_ok` selectors.

## Accept
One glyph source; screens render unchanged under fixtures.

## Proof
Unit/pty smoke · STATUS SHA `8facad9` on origin. Push waits Accept (product already SHIPped).

## Refs
CC Zone-A · hub Accept @ 06:33:34Z
