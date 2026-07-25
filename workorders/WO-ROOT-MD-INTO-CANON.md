# WO-ROOT-MD-INTO-CANON

**Status:** DONE (this tip)  
**Posted:** Max GO 2026-07-25 — fold root markdown into OKF

## Goal

Get `DESIGN.md` and `priority_engine.md` out of the git repo root by folding into `canon/` OKF.

## Scope

- Fold unique DESIGN bits (MCP-ready) into `canon/architecture/session-engine.md`
- Confirm priority catalog already lives in `canon/engine/priority-engine.md`; retarget citations
- Delete root `DESIGN.md` + `priority_engine.md`
- Update live pointers (north-star, settle-detection, trainer-cockpit, testing catalog/cases, `tests/test_classify.py`)
- Stamp `canon/findings.md` + `canon/DECISIONS.md`

## Constraints

- DOCS WIN: reborn north-star / stop-on-unknown wins over AI-live-driver DESIGN framing
- No product behavior change (docstring pointer only in `test_classify.py`)
- Do not grow `docs/` or new root design dumps

## Accept

- Root files gone
- Content reachable from `canon/index.md` owning concepts
- `rg 'DESIGN\.md|priority_engine\.md'` clean of live root-file pointers (historical DESIGN-v2 mentions OK)

## Proof

STATUS + SHA; list deleted + updated paths.
