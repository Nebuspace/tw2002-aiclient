---
type: Reference
title: Test Cases — test_crawl_start_protocol
description: protocol.py's `crawl_start` verb dispatch -- no network, same bare dispatch-harness convention as tests/test_protocol_haggle.py/ test_actor_attribution.py.
resource: repo://tw2002-aiclient/tests/test_crawl_start_protocol.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_crawl_start_protocol.py`

_protocol.py's `crawl_start` verb dispatch -- no network, same bare dispatch-harness convention as tests/test_protocol_haggle.py/ test_actor_attribution.py._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_crawl_start_missing_profile_arg` | Crawl start missing profile arg. |
| `test_crawl_start_unknown_profile_name` | Crawl start unknown profile name. |
| `test_crawl_start_refuses_non_sacrificial_profile` | Crawl start refuses non sacrificial profile. |
| `test_crawl_start_missing_path_or_log_path` | Crawl start missing path or log path. |
| `test_crawl_start_refused_while_human_is_attached` | Crawl start refused while human is attached. |
| `test_crawl_start_dispatches_and_returns_the_crawl_summary` | Crawl start dispatches and returns the crawl summary. |
