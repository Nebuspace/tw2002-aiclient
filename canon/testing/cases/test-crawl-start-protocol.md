---
type: Reference
title: Test Cases — Crawl Start Protocol
description: protocol.
resource: repo://tw2002-aiclient/tests/test_crawl_start_protocol.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_crawl_start_protocol.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_protocol.py's `crawl_start` verb dispatch -- no network, same bare_

| Test | Blurb |
|------|-------|
| `test_crawl_start_missing_profile_arg` | Crawl start missing profile arg. |
| `test_crawl_start_unknown_profile_name` | Crawl start unknown profile name. |
| `test_crawl_start_refuses_non_sacrificial_profile` | Crawl start refuses non sacrificial profile. |
| `test_crawl_start_missing_path_or_log_path` | Crawl start missing path or log path. |
| `test_crawl_start_refused_while_human_is_attached` | Crawl start refused while human is attached. |
| `test_crawl_start_dispatches_and_returns_the_crawl_summary` | Crawl start dispatches and returns the crawl summary. |
