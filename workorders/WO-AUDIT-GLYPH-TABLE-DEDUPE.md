# WO-AUDIT-GLYPH-TABLE-DEDUPE — Import thin glyphs from draw.py

> Status: **DRAFT** 2026-07-25 · from CC POLISH Zone-A BANK · tip `88004d8`  
> Type: polish · Priority: P2 · Lens: L4  
> Refs: `screens.py:222-239` · `cockpit/draw.py` THIN_*

## Goal
Stop byte-duplicating thin glyph tables in `screens.py`; import + extend from `draw.py` (+ `sel` key if needed).

## Scope
- A: `screens.py` — import tables
- B: `cockpit/draw.py` — single source
- C: grep proof no duplicate constants

## Constraints
Docs/visual parity only; no seat-key changes.

## Accept
One glyph source; screens render unchanged under fixtures.

## Proof
Unit/pty smoke · STATUS. Push waits Accept.
