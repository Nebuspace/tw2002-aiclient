# WO-AUDIT-UNICODE-OK-DOCSTRING — Fix stale screens._unicode_ok locale claim

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`922739b`** (CC · rebased from `3404f81` onto Cursor docs tip) · docs stamp Cursor  
> Type: docs/polish · Priority: P3 · Lens: L2/L4  
> Refs: CC GLYPH STATUS @ 06:32:45Z · hub banked ⏳ @ 06:33:34Z · Accept @ 11:30:32Z

## Tip verdict
**DONE** on origin `922739b` — locale lie retired; `screens._unicode_ok` is a thin identity delegate onto `draw.unicode_ok` (local name kept for call sites). Licensed by 15-case env grid (pre-fix vs draw agree); 3-leg pin (identity · unconditional · grid) + new `tests/test_unicode_ok_delegation.py`. Suite **1918/0/0** at Accept. Hub nit: commit prose said 23 pins / collect 22 — informational.

## Goal
Align `screens._unicode_ok` docstring with code: it claimed a locale preference the implementation never performs. Truth table matches `draw.unicode_ok` (env-flag-only) — docstring honesty + safe 1:1 delegate.

## Scope
- A: `screens.py` — docstring + thin wrap to `draw.unicode_ok`
- B: pin that docs claim matches behavior / delegation cannot silently fork
- C: do **not** change glyph tables (already DONE in `8facad9`)

## Constraints
No seat-key / attach / Human→App. No silent selector behavior change. Tripwire untouched.

## Accept
Docstring (or delegation) matches actual env-flag behavior; no locale claim without code.

## Proof
Hub Accept @ 11:30:32Z · origin tip `922739b` (`ls-remote`). Push waits Accept (product already SHIPped).
