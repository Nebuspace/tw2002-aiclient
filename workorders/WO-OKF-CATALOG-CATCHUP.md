# WO-OKF-CATALOG-CATCHUP

**Status:** DONE / closed via later catalog tips (see STATUS history)  
**Posted:** 2026-07-25T15:27:10Z

## Goal

Close OKF catalog lag — active `tests/test_*.py` modules missing `canon/testing/cases/*.md` (+ index blur if needed).

## Scope

`canon/testing/**` docs only · no product `.py` · no pytest.ini.

## Method

Diff `ls tests/test_*.py` vs `canon/testing/cases/`; add case files for uncatalogued actives (priority: attach/keydrop/tx-record/menumap/unencodable/loops/menu_crawl family from AUDIT report + any new since).

## Accept

Every active collectable module has a case file OR an explicit BANKED deferral row in the catalog index with reason.

## Refs

- `AUDIT-TEST-SUITE-DUP-POINTLESS.md` CATALOG-GAP
- Catalog tip family from 2026-07-25 wave
