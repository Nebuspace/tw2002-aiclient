---
type: Reference
title: Test Cases — Game Knowledge
description: Game Knowledge Store tests (TW-25) -- no network, tmp_path only,.
resource: repo://tw2002-aiclient/tests/test_game_knowledge.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_game_knowledge.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Game Knowledge Store tests (TW-25) -- no network, tmp_path only,_

| Test | Blurb |
|------|-------|
| `test_knowledge_path_uses_world_id_to_build_the_slug_directory` | Knowledge path uses world id to build the slug directory. |
| `test_knowledge_path_differs_for_different_identity_triples` | Knowledge path differs for different identity triples. |
| `test_load_knowledge_missing_file_returns_fresh_empty_structure` | Load knowledge missing file returns fresh empty structure. |
| `test_save_then_load_round_trips` | Save then load round trips. |
| `test_save_knowledge_creates_file_with_0600_permissions` | Save knowledge creates file with 0600 permissions. |
| `test_save_knowledge_leaves_no_temp_file_after_success` | Save knowledge leaves no temp file after success. |
| `test_save_knowledge_atomic_write_survives_a_crash_before_rename` | Save knowledge atomic write survives a crash before rename. |
| `test_save_knowledge_removes_orphaned_tmp_file_on_write_failure` | Save knowledge removes orphaned tmp file on write failure. |
| `test_load_knowledge_raises_on_truncated_json` | Load knowledge raises on truncated json. |
| `test_load_knowledge_raises_on_empty_file` | Load knowledge raises on empty file. |
| `test_load_knowledge_raises_on_unsupported_version` | Load knowledge raises on unsupported version. |
| `test_load_knowledge_never_silently_resets_a_corrupt_file_to_empty` | Load knowledge never silently resets a corrupt file to empty. |
| `test_upsert_menu_node_creates_new_node_with_first_and_last_seen` | Upsert menu node creates new node with first and last seen. |
| `test_upsert_menu_node_is_idempotent_and_updates_last_seen_not_first_seen` | Upsert menu node is idempotent and updates last seen not first seen. |
| `test_upsert_menu_node_without_label_preserves_prior_label` | Upsert menu node without label preserves prior label. |
| `test_upsert_menu_node_refuses_empty_signature` | Upsert menu node refuses empty signature. |
| `test_get_menu_node_returns_none_when_unseen` | Get menu node returns none when unseen. |
| `test_get_menu_node_returns_a_copy_not_a_live_reference` | Get menu node returns a copy not a live reference. |
| `test_upsert_menu_edge_creates_new_edge` | Upsert menu edge creates new edge. |
| `test_upsert_menu_edge_same_from_node_and_key_updates_in_place` | Upsert menu edge same from node and key updates in place. |
| `test_upsert_menu_edge_refuses_invalid_kind` | Upsert menu edge refuses invalid kind. |
| `test_upsert_menu_edge_refuses_empty_required_fields` | Upsert menu edge refuses empty required fields. |
| `test_find_menu_path_trivial_same_node` | Find menu path trivial same node. |
| `test_find_menu_path_direct_edge` | Find menu path direct edge. |
| `test_find_menu_path_multi_hop_shortest_path` | Find menu path multi hop shortest path. |
| `test_find_menu_path_returns_none_when_unreachable` | Find menu path returns none when unreachable. |
| `test_find_menu_path_ignores_cycles` | Find menu path ignores cycles. |
| `test_upsert_game_data_row_stamps_source_and_last_verified_ts` | Upsert game data row stamps source and last verified ts. |
| `test_upsert_game_data_row_preserves_list_valued_fields` | special_abilities is explicitly a list-of-string field per. |
| `test_upsert_game_data_row_same_key_updates_in_place` | Upsert game data row same key updates in place. |
| `test_upsert_game_data_row_refuses_unknown_table` | Upsert game data row refuses unknown table. |
| `test_upsert_game_data_row_refuses_empty_key` | Upsert game data row refuses empty key. |
| `test_upsert_game_data_row_refuses_empty_source` | Upsert game data row refuses empty source. |
| `test_upsert_game_data_row_refuses_non_dict_fields` | Upsert game data row refuses non dict fields. |
| `test_get_game_data_row_returns_none_when_unseen` | Get game data row returns none when unseen. |
| `test_get_game_data_row_returns_a_copy_not_a_live_reference` | Get game data row returns a copy not a live reference. |
| `test_list_game_data_rows_scoped_to_its_own_table` | List game data rows scoped to its own table. |
| `test_cross_world_isolation_menu_map_never_bleeds_between_worlds` | Two different characters on the same host+game are two. |
| `test_cross_world_isolation_game_data_never_bleeds_between_worlds` | Cross world isolation game data never bleeds between worlds. |
| `test_cross_world_isolation_same_host_and_game_different_handle_is_a_different_world` | The precise collision this store must avoid: host+game_letter. |
| `test_knowledge_lock_real_flock_blocks_second_acquirer_until_released` | Knowledge lock real flock blocks second acquirer until released. |
| `test_real_concurrent_menu_node_upsert_across_many_threads_never_loses_an_update` | Acceptance bar (mirrors player_bank. |
| `test_real_concurrent_game_data_row_upsert_across_many_threads_never_loses_an_update` | Real concurrent game data row upsert across many threads never loses an update. |
