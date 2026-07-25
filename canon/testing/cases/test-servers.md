---
type: Reference
title: Test Cases — Servers
description: WO-MS-1 server catalog tests.
resource: repo://tw2002-aiclient/tests/test_servers.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_servers.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_WO-MS-1 server catalog tests._

| Test | Blurb |
|------|-------|
| `test_catalog_has_39_servers` | MS-3c: live catalog pruned to twgs-direct/online (49→39). |
| `test_front_end_values_are_contract` | Front end values are contract. |
| `test_get_server_and_resolve` | Get server and resolve. |
| `test_adding_server_is_catalog_edit_only` | Accept criterion: new server = toml edit, zero code change. |
| `test_profile_resolves_via_server_key` | Profile resolves via server key. |
| `test_profile_host_port_backcompat` | Profile host port backcompat. |
| `test_bad_front_end_rejected` | Bad front end rejected. |
