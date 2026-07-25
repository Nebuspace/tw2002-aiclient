# WO-AUDIT-UNICODE-OK-DOCSTRING — Fix stale screens._unicode_ok locale claim

> Status: **DRAFT** 2026-07-25 · banked from GLYPH-TABLE Accept · tip `8facad9`  
> Type: docs/polish · Priority: P3 · Lens: L2/L4  
> Refs: CC GLYPH STATUS @ 06:32:45Z · hub banked ⏳ @ 06:33:34Z

## Goal
Align `screens._unicode_ok` docstring with code: it claims a locale preference the implementation never performs. Truth table matches `draw.unicode_ok` (env-flag-only) for every env state — either fix the docstring, or safely delegate 1:1 to draw (doc-fix preferred unless hub opens product).

## Scope
- A: `screens.py` — docstring (and optional thin wrap to `draw.unicode_ok`)
- B: optional one-line test that docs claim matches behavior
- C: do **not** change glyph tables (already DONE in `8facad9`)

## Constraints
No seat-key / attach / Human→App. No silent selector behavior change. Tripwire untouched.

## Accept
Docstring (or delegation) matches actual env-flag behavior; no locale claim without code.

## Proof
Diff review · suite green. Push waits Accept.
