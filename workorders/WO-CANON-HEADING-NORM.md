# WO-CANON-HEADING-NORM — specify heading-citation checker normalisation

**Status:** OPEN · READY  
**Posted:** 2026-07-27T19:47:00Z · hub (from CC PROCESS-NOTE after #113)  
**Seat:** `impl-claudecode-aiclient` (HOLD-capacity · docs-only · authored the parent WO)  
**Depends:** `main` ≥ `b2e586d` (#113 heading conversion DONE)  
**Refs:** `workorders/WO-CANON-HEADING-CITATIONS.md` · CC PROCESS-NOTE 2026-07-27T20:32:40Z

## Goal

Amend `WO-CANON-HEADING-CITATIONS.md` (and any standing Proof / checker note it owns) so
**"heading is present"** is unambiguous. Two competent checkers disagreed on #113 (0 vs 2)
because the Accept criterion did not define normalisation.

## Spec to land in the WO

When comparing a `§"…"` cite to a canon heading:

1. **Strip inline markdown** from both sides before compare (at least backticks / code spans).
2. **Compare dashes literally** — ASCII `--` ≠ Unicode em-dash `—` (do not fold).
3. **Collapse whitespace** (trim ends; squeeze internal runs to a single space).

Do **not** change product cites in this WO unless a one-line residual is required to match
the newly explicit rule (prefer leave tree as #113 left it; this WO is the rule, not a
re-sweep).

## Scope

- `workorders/WO-CANON-HEADING-CITATIONS.md` (Proof / Accept amendment)
- Optional: this file stamped DONE when merged
- **No** `canon/` edits · **No** product behaviour · **No** #93 unpark

## Accept

1. WO text states the three normalisation rules above in Proof (or Accept).
2. Explicit: strip backticks · dashes literal · whitespace collapse.
3. PR + STATUS with SHA.

## Proof

Docs-only · suite n/a or unchanged · `gh pr view` state MERGED before any Accept ACK.
