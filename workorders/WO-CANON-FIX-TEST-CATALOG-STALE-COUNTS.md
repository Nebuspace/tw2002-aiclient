# WO-CANON-FIX-TEST-CATALOG-STALE-COUNTS

**Status:** IN_PROGRESS  
**Priority:** LOW (queue-aiclient READY · ungated)  
**Depends-on:** none  
**gated:** no · **schema:** n/a

## Goal

Re-verify and correct the headline module/test counts in
`canon/testing/test-case-catalog.md` against tip `origin/main` (post-#642).
Per-module blurbs may still lag — this WO only fixes the stale headline census.

## Scope

- `canon/testing/test-case-catalog.md` — timestamp + collect census block
- this WO file

## Out of scope

- Regenerating every per-module OKF case blurb
- Changing `pytest.ini` ignore list
- Any product code

## Accept

1. Headline counts match a fresh tip collect:
   - `pytest -n0 --collect-only` footer test count
   - `-q` line count of `tests/test_*.py:`
   - on-disk `tests/test_*.py` file count
   - BANKED ignores still named and excluded from the active total
2. live-prove `n/a` (docs-only census).

## Proof

```bash
.venv/bin/python -m pytest -n0 --collect-only   # footer
.venv/bin/python -m pytest -n0 --collect-only -q | rg -c '^tests/test_.*\.py:'
git ls-files 'tests/test_*.py' | wc -l
```

Verified on tip `eb8129f9` (worktree): **7480** collected · **311** active modules ·
**312** on-disk · **1** BANKED (`test_crawl_start_protocol.py`; analyze BANK-DELETED by WO-CLEANUP-BANK-DELETE-TWCLIENT-ANALYZE-SUITE). Historical Accept below recorded 313/2 at #644 merge.
