---
type: Reference
title: Test Cases — test_cli_crawl_wiring
description: `tw crawl` CLI verb wiring -- argparse only (dispatch itself needs a live daemon and is exercised at the protocol layer instead, see tests/test_crawl_start_protocol.py).
resource: repo://tw2002-aiclient/tests/test_cli_crawl_wiring.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cli_crawl_wiring.py`

_`tw crawl` CLI verb wiring -- argparse only (dispatch itself needs a live daemon and is exercised at the protocol layer instead, see tests/test_crawl_start_protocol.py)._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_crawl_verb_is_wired_with_expected_defaults` | Crawl verb is wired with expected defaults. |
| `test_crawl_verb_requires_profile` | Crawl verb requires profile. |
| `test_crawl_verb_accepts_overrides` | Crawl verb accepts overrides. |
