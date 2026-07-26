# WO-BANNER-STAMP-SWEEP-POST-SPRINT — Docs-only banner sweep after M1–M4 sprint

**Status:** READY · LOW · Cursor
**Posted:** 2026-07-26
**Seat:** Cursor

## Goal

Docs-only sweep: find any remaining `OPEN` / `IN FLIGHT` / `IN PROGRESS` / `READY` banners in
`workorders/` whose **product is already on `main`** after the M1–M4 sprint stamps (see
WO-EXPLORE-SECTOR-FRONTIER, WO-RUN-DIR-NORMALISE, WO-TUI-HELP-ARGV, WO-MICRO-LOGIN-BLANK-REJECT,
WO-CONTROL-LOCK-AUTOLOOP-FENCE, WO-README-PLAYER-VOICE, WO-P2-G3-LOOPS — all DONE as of
2026-07-26).  Stamp only what is provably on `main`; leave uncertain ones alone.

## Scope

- `workorders/WO-*.md` — status banner lines only
- `git log --oneline` on `main` is the evidence source

## Constraints

- **Docs only — no product Python changes**
- Verify each WO against `git log` before stamping; do not stamp on assumption
- Do not stamp WOs whose product is not yet merged (e.g. banked/gated items)
- Skip WOs already DONE / SUPERSEDED / BANKED

## Accept

1. Any WO banner still showing OPEN/IN-FLIGHT/IN-PROGRESS/READY whose product is confirmed on
   `main` is updated to **DONE · `<sha>`**.
2. No WO is stamped whose product is not confirmed on `main`.
3. Report lists every WO examined (STAMPED vs SKIPPED-reason).

## Proof

`git log --oneline` citation per stamped WO in STATUS report.  No product file diffs — only
`workorders/WO-*.md` in the PR diff.
