---
type: Reference
title: Test Cases — test_analyze
description: Archive TW-12 session-retro analyzer suite — BANK-DELETED (no tip twclient.analyze).
resource: repo://tw2002-aiclient/tests/test_analyze.py
tags: [testing, catalog, pytest, inventory, bank-deleted]
timestamp: 2026-08-10T04:12:00Z
---

# Test Cases — `tests/test_analyze.py`

_Archive TW-12 session-retro analyzer tests (synthetic ledger)._

> **BANK-DELETED** (WO-CLEANUP-BANK-DELETE-TWCLIENT-ANALYZE-SUITE, 2026-08-10) —
> file removed. It imported deleted `twclient.analyze` and could not collect on
> tip after ADR-001. Rebirth twins: `tw mine` / `miner.py`, `tw teach analyze`,
> `tw report`. Historical case names kept below for archaeology only.

| Test | Blurb |
|------|-------|
| `test_select_by_capture_name` | Select by capture name. |
| `test_select_by_ts_prefix` | Select by ts prefix. |
| `test_select_all` | Select all. |
| `test_analyze_surfaces_profitable_candidates` | Analyze surfaces profitable candidates. |
| `test_analyze_empty_session` | Analyze empty session. |
