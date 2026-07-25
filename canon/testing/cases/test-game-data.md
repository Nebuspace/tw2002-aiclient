---
type: Reference
title: Test Cases — Game Data
description: TW-24 game_data schema/loader tests.
resource: repo://tw2002-aiclient/tests/test_game_data.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_game_data.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_TW-24 game_data schema/loader tests._

| Test | Blurb |
|------|-------|
| `test_load_fixture_scout_is_introspected` | Load fixture scout is introspected. |
| `test_reject_authored_source` | Reject authored source. |
| `test_reject_missing_max_holds` | Reject missing max holds. |
| `test_empty_game_data_has_no_ships` | Empty game data has no ships. |
| `test_ship_row_to_spec_bridge` | Ship row to spec bridge. |
