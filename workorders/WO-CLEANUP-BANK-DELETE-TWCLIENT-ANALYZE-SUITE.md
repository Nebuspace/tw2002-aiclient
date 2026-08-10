# WO-CLEANUP-BANK-DELETE-TWCLIENT-ANALYZE-SUITE — BANK-DELETE archive twclient analyze suite

**Status:** DONE (this PR) · Cursor · `wo/CLEANUP-BANK-DELETE-TWCLIENT-ANALYZE-SUITE`
**Posted:** residual of DONE WO-CLEANUP-UNIGNORE-HAGGLE-LEDGER-SUITE /
WO-FIX-DELETED-TWCLIENT-IMPORTS-COLLECTION-BREAK · verify-first after #656

## Goal

Remove `tests/test_analyze.py`, which still `from twclient.analyze import …`
after ADR-001 deleted the sibling package. It cannot collect on tip and was
only kept behind `pytest.ini --ignore`.

## Disposition (verify-first)

| Tip fact | Ruling |
|---|---|
| `tests/test_analyze.py` imports deleted `twclient.analyze` | BANK-DELETE (no rewrite) |
| Archive `tw analyze` session-retro (`analyze_session` / `format_report`) | No rebirth CLI verb |
| Live twins | `tw mine` / `miner.py` (ledger mining → drafts); `tw teach analyze` (AI teacher); `tw report` (post-session digest) |
| `tests/test_crawl_start_protocol.py` | KEEP ignored (daemon crawl verb still unwired) |

Same BANK-DELETE class as WO-FIX-DELETED-TWCLIENT-IMPORTS-COLLECTION-BREAK (#168–#176 pattern).
Do **not** restore an archive-shaped `tw analyze` verb in this pass.

## Accept

1. `tests/test_analyze.py` deleted; its `--ignore=` line gone.
2. Default ignore census is only `tests/test_crawl_start_protocol.py`.
3. Catalog / findings / AUDIT landmine row tip-stamped; suite collects with 0 ERRORS.
4. live-prove `n/a` (offline suite hygiene).

## Refs

- ADR-001 · `pytest.ini` · `workorders/AUDIT-TEST-IGNORE-LIST-LANDMINE.md`
- `canon/testing/test-case-catalog.md`
