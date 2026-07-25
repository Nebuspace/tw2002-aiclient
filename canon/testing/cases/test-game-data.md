---
type: Reference
title: Test Cases — test_game_data
description: TW-24 game_data schema/loader tests.
resource: repo://tw2002-aiclient/tests/test_game_data.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_game_data.py`

_TW-24 game_data schema/loader tests._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_load_fixture_scout_is_introspected` | Load fixture scout is introspected. |
| `test_reject_authored_source` | Reject authored source. |
| `test_reject_missing_max_holds` | Reject missing max holds. |
| `test_empty_game_data_has_no_ships` | Empty game data has no ships. |
| `test_ship_row_to_spec_bridge` | Ship row to spec bridge. |
