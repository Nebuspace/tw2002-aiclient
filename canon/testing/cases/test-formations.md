---
type: Reference
title: Test Cases — Formations
description: TW-16 formation detector tests.
resource: repo://tw2002-aiclient/tests/test_formations.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_formations.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_TW-16 formation detector tests._

| Test | Blurb |
|------|-------|
| `test_dead_end` | Dead end. |
| `test_bubble_single_entrance` | Bubble single entrance. |
| `test_one_way_warp` | One way warp. |
| `test_warp_sink_no_exit` | Warp sink no exit. |
| `test_catalog_world_and_write_membership` | Catalog world and write membership. |
| `test_membership_map_dedupes_kinds` | Membership map dedupes kinds. |
