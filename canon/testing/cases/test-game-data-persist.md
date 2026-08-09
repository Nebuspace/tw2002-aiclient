---
type: Reference
title: Test Cases — test_game_data_persist
description: REMOVED — historical inventory; tip module absent. TW-26/27 write lane -- persist/query path tests for `game_data.py`'s bridge over `game_knowledge.py`'s per-world "ships" game-data table.
resource: repo://tw2002-aiclient/tests/test_game_data_persist.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_game_data_persist.py`

_TW-26/27 write lane -- persist/query path tests for `game_data.py`'s bridge over `game_knowledge.py`'s per-world "ships" game-data table._

> **REMOVED** — module absent on tip (not merely pytest-ignored). Catalogued for completeness (historical inventory).
| Test | Blurb |
|------|-------|
| `test_persist_ship_row_then_get_ship_round_trips` | Persist ship row then get ship round trips. |
| `test_persist_ship_row_preserves_list_and_none_valued_fields` | Persist ship row preserves list and none valued fields. |
| `test_persist_ship_row_writes_into_the_existing_game_knowledge_store` | Not a second/parallel store -- the row must land inside the SAME per-world game_knowledge.json the menu-map graph already lives in. |
| `test_persist_ship_row_stamps_last_verified_ts_for_a_tsless_introspector_row` | Persist ship row stamps last verified ts for a tsless introspector row. |
| `test_get_ship_returns_none_when_unseen` | Get ship returns none when unseen. |
| `test_list_ships_empty_for_a_world_with_no_persisted_ships` | List ships empty for a world with no persisted ships. |
| `test_list_ships_returns_every_persisted_ship` | List ships returns every persisted ship. |
| `test_persist_ship_row_rejects_non_introspected_source` | Persist ship row rejects non introspected source. |
| `test_persist_ship_row_rejects_missing_required_field` | Persist ship row rejects missing required field. |
| `test_persist_ship_row_rejection_does_not_clobber_an_existing_good_row` | A later rejected write for the SAME ship must not touch the already-persisted good row -- validation runs before any lock/write. |
| `test_persist_ship_row_newer_capture_supersedes_older_row` | Persist ship row newer capture supersedes older row. |
| `test_cross_world_isolation_ships_never_bleed_between_worlds` | Cross world isolation ships never bleed between worlds. |
| `test_cross_world_isolation_same_ship_name_different_values_per_world` | Two worlds may each introspect a ship of the same name with DIFFERENT server-specific numbers -- neither may overwrite the other's row. |
| `test_list_flyable_ships_ungated_ship_always_passes` | List flyable ships ungated ship always passes. |
| `test_list_flyable_ships_gated_ship_requires_sufficient_alignment` | List flyable ships gated ship requires sufficient alignment. |
| `test_list_flyable_ships_unknown_alignment_only_passes_ungated_ships` | List flyable ships unknown alignment only passes ungated ships. |
| `test_real_concurrent_persist_ship_row_across_many_threads_never_loses_an_update` | Real concurrent persist ship row across many threads never loses an update. |
| `test_persist_cargo_hold_price_then_get_round_trips` | Persist cargo hold price then get round trips. |
| `test_persist_cargo_hold_price_writes_into_the_existing_game_knowledge_store` | Persist cargo hold price writes into the existing game knowledge store. |
| `test_persist_cargo_hold_price_stamps_last_verified_ts_for_a_tsless_introspector_row` | Persist cargo hold price stamps last verified ts for a tsless introspector row. |
| `test_get_cargo_hold_price_returns_none_when_never_persisted` | Get cargo hold price returns none when never persisted. |
| `test_persist_cargo_hold_price_rejects_non_introspected_source` | Persist cargo hold price rejects non introspected source. |
| `test_persist_cargo_hold_price_rejects_missing_required_field` | Persist cargo hold price rejects missing required field. |
| `test_persist_cargo_hold_price_newer_capture_supersedes_older_row` | Persist cargo hold price newer capture supersedes older row. |
| `test_cross_world_isolation_cargo_hold_price_never_bleeds_between_worlds` | Cross world isolation cargo hold price never bleeds between worlds. |
