# WO-CLEANUP-UNIGNORE-HAGGLE-LEDGER-SUITE — drop false `--ignore` landmines

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-UNIGNORE-HAGGLE-LEDGER-SUITE`  
**Posted:** post-#528 idle pick · queue READY batch owned by CC / gated / ghost

## Goal

Un-ignore `tests/test_haggle.py` and `tests/test_ledger.py` in `pytest.ini`.
Both already import `tw2002_aiclient` (not archive `twclient`), collect cleanly, and
pass when run directly — the standing `--ignore` lines are landmines from the
pre-port KEEP bucket in `AUDIT-TEST-IGNORE-LIST-LANDMINE.md`.

## Disposition (verify-first)

| File | Tip fact | Action |
|---|---|---|
| `tests/test_haggle.py` | `from tw2002_aiclient.session.haggle import …` | drop `--ignore` |
| `tests/test_ledger.py` | `from tw2002_aiclient.ledger import …` | drop `--ignore` |
| `tests/test_analyze.py` | still `from twclient.analyze` | **BANK-DELETED** by WO-CLEANUP-BANK-DELETE-TWCLIENT-ANALYZE-SUITE (was KEEP) |
| `tests/test_crawl_start_protocol.py` | still `from twclient` (daemon crawl unwired) | KEEP ignored |

## Out of bounds

- Rewriting `test_analyze.py` / `test_crawl_start_protocol.py`
- Touching haggle/ledger product code
- Restoring crawl/haggle CLI verbs

## Accept

1. Two `--ignore=` lines gone; comment census updated.
2. Default `pytest --collect-only` includes both files with 0 collection ERRORS.
3. Targeted + full (or xdist) suite green.
4. live-prove `n/a` (offline suite hygiene).

## Refs

- `pytest.ini` · `workorders/AUDIT-TEST-IGNORE-LIST-LANDMINE.md`
- Same class as #149 false-ignored un-ignore · #474 BANK-DELETE (different files)
