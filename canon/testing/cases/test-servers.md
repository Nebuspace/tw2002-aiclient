---
type: Reference
title: Test Cases — test_servers
description: REMOVED — historical inventory; tip module absent. WO-MS-1 server catalog tests.
resource: repo://tw2002-aiclient/tests/test_servers.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_servers.py`

_WO-MS-1 server catalog tests._

> **REMOVED** — module absent on tip (not merely pytest-ignored). Catalogued for completeness (historical inventory).
| Test | Blurb |
|------|-------|
| `test_catalog_has_39_servers` | MS-3c: live catalog pruned to twgs-direct/online (49→39). |
| `test_front_end_values_are_contract` | Front end values are contract. |
| `test_get_server_and_resolve` | Get server and resolve. |
| `test_adding_server_is_catalog_edit_only` | Accept criterion: new server = toml edit, zero code change. |
| `test_profile_resolves_via_server_key` | Profile resolves via server key. |
| `test_profile_host_port_backcompat` | Profile host port backcompat. |
| `test_bad_front_end_rejected` | Bad front end rejected. |
