---
type: Reference
title: Test Cases — Cli Crawl Wiring
description: `tw crawl` CLI verb wiring -- argparse only (dispatch itself needs a.
resource: repo://tw2002-aiclient/tests/test_cli_crawl_wiring.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cli_crawl_wiring.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_`tw crawl` CLI verb wiring -- argparse only (dispatch itself needs a_

| Test | Blurb |
|------|-------|
| `test_crawl_verb_is_wired_with_expected_defaults` | Crawl verb is wired with expected defaults. |
| `test_crawl_verb_requires_profile` | Crawl verb requires profile. |
| `test_crawl_verb_accepts_overrides` | Crawl verb accepts overrides. |
