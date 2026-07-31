# WO-FOLD-EMPTY-DECISIONS-DOC

**Status:** READY · EXECUTE · LOW · comment-only (hub note from #285 Accept)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/FOLD-EMPTY-DECISIONS-DOC`
**Depends:** `main` ≥ `bf3c268` (#285 calm-empty HELP)

## Goal

Update `cockpit/fold.py` module/doc comments that still cite the old
DECISIONS empty marker `["—", "Exploring…"]`. Runtime already compares to
`compose_decisions_lines(None, …)` (dynamic) — comments only drifted after #285.

## Scope

- `tw2002_aiclient/cockpit/fold.py` docstring / comments only
- Optionally mirror wording in any test comments that hard-code the old pair
  as *canon* (not as assertions already updated in #285)
- `workorders/WO-FOLD-EMPTY-DECISIONS-DOC.md`

## Accept

1. No remaining fold.py prose claims the two-line Exploring empty as current.
2. No product behavior change · suite green · live-prove **n/a**.

## Constraints

Comment/docs only.

## Refs

- #285 Accept craft note · `compose_decisions_lines` calm-empty HELP
