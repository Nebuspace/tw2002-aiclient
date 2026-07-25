# WO-AUDIT-SAFE-WIDTH-DOCSTRING — Document `_safe_width` contract

> Status: **DRAFT** 2026-07-25 · Zone-A micro-bank · tip `00cb9e8`  
> Type: docs/polish · Priority: P3 · Lens: L4  
> Refs: CC POLISH Zone-A bank · hub optional micro list

## Goal
Add/clarify the docstring on `_safe_width` (or equivalent cell-width helper) so call sites know clip vs measure semantics — no behavior change.

## Scope
- A: one helper docstring only (path confirmed at execute — likely `cockpit/draw.py` or `screens.py`)
- B: no test change unless docstring asserts a false contract

## Constraints
Docs/comment only unless hub opens a behavior WO. Stay clear of SAFE-ADDSTR mid-edit lanes until that WO CLOSES. No seat-key / Human→App.

## Accept
Docstring matches actual clip/measure behavior; reviewers can cite it without reading call graph.

## Proof
Diff review · suite green (no functional delta). Push waits Accept.
