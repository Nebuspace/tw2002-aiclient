---
type: Reference
title: Test Cases — test_analyze
description: TW-12 session-retro analyzer tests — no network, synthetic ledger only.
resource: repo://tw2002-aiclient/tests/test_analyze.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_analyze.py`

_TW-12 session-retro analyzer tests — no network, synthetic ledger only._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_select_by_capture_name` | Select by capture name. |
| `test_select_by_ts_prefix` | Select by ts prefix. |
| `test_select_all` | Select all. |
| `test_analyze_surfaces_profitable_candidates` | Analyze surfaces profitable candidates. |
| `test_analyze_empty_session` | Analyze empty session. |
