# WO-CANON-DRAFT-TEST-CATALOG-HEADLINE-REFRESH

**Goal:** Refresh stale headline census in `canon/testing/test-case-catalog.md`
and `canon/index.md`, and add the missing per-module OKF case stub for
`tests/test_coach_provenance.py`.

**Depends-on:** none (docs-only)

**Scope:**
- `canon/testing/test-case-catalog.md` — headline collect counts + timestamp
- `canon/index.md` — Testing index blurb counts
- `canon/testing/cases/test-coach-provenance.md` — new case stub (4 tests)
- this WO file

**Out of scope:** regenerating every per-module case file; product code.

**Accept:**
1. Headline counts match tip `pytest -n0 --collect-only` footer and quiet
   module-line count (BANKED ignore accounted for).
2. `test-coach-provenance.md` lists all four tip `test_*` functions.
3. No product code changes.

**Proof:** tip collect-only footer pasted in the catalog; case file exists.
Live: n/a (docs-only).
