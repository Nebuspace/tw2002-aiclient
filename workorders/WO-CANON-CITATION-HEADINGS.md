# WO-CANON-CITATION-HEADINGS — Cite canon by section heading, not line number

**Status:** OPEN · READY  
**Posted:** 2026-07-27T19:12:00Z · from #109 STOP-THE-LINE + CC verify  
**Seat:** prefer Claude Code (offered; mechanical) or Cursor  
**Depends:** main ≥ `3854e70` (#109 citation episode)  
**Tip-check:** 25+ `*.md:<n>` citations in `tw2002_aiclient/`; line numbers break on ordinary canon edits.

## Goal

Convert product-code canon citations from `file.md:LINE` to **section-heading** (or stable anchor) form that survives insertions. Also repair pre-existing blank citations:
- `app.py` → `spectate-and-attach.md:91` / `:100` (blank on main before #109)

## Scope

- Citation sites under `tw2002_aiclient/` (+ tests that assert citation strings if any)
- Optional tiny helper/docs note on preferred citation form
- Do **not** rewrite canon prose beyond what's needed for clear headings/anchors

## Accept

1. No remaining brittle line-only citations for the converted set (or explicit inventory of exceptions with reason).
2. The three `app.py`/`spectate-and-attach` blanks resolve to real claimed text (or honest removal if obsolete).
3. Suite green; a deliberate canon insertion above a cited heading does not break the citation (pin or argued equivalent).

## Proof

Suite + before/after sample of citation strings; live-prove n/a.
