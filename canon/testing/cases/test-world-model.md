---
type: Reference
title: Test Cases — World Model
description: World model tests (TW-06) -- no network, tmp_path only, never.
resource: repo://tw2002-aiclient/tests/test_world_model.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_world_model.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_World model tests (TW-06) -- no network, tmp_path only, never_

| Test | Blurb |
|------|-------|
| `test_load_sector_file_missing_returns_none` | Load sector file missing returns none. |
| `test_save_then_load_sector_file_round_trips` | Save then load sector file round trips. |
| `test_save_sector_file_leaves_no_temp_file_after_success` | Save sector file leaves no temp file after success. |
| `test_save_sector_file_creates_file_with_0600_permissions` | Save sector file creates file with 0600 permissions. |
| `test_upsert_sector_atomic_write_survives_a_crash_before_rename` | Upsert sector atomic write survives a crash before rename. |
| `test_upsert_sector_removes_orphaned_tmp_file_on_write_failure` | Upsert sector removes orphaned tmp file on write failure. |
| `test_load_sector_file_raises_on_truncated_json` | Load sector file raises on truncated json. |
| `test_load_sector_file_raises_on_empty_file` | Load sector file raises on empty file. |
| `test_load_sector_file_raises_on_non_object_shape` | Load sector file raises on non object shape. |
| `test_load_sector_file_raises_on_missing_sector_id` | Load sector file raises on missing sector id. |
| `test_a_corrupt_sector_does_not_block_a_DIFFERENT_sector` | Per-sector granularity means a corrupt sector 1 must not prevent. |
| `test_upsert_then_get_round_trips` | Upsert then get round trips. |
| `test_get_sector_returns_none_for_unknown_sector` | Get sector returns none for unknown sector. |
| `test_upsert_sector_defaults_unspecified_fields_on_first_write` | Upsert sector defaults unspecified fields on first write. |
| `test_upsert_sector_requires_sector_id` | Upsert sector requires sector id. |
| `test_get_sector_returns_a_copy_not_a_live_reference` | Get sector returns a copy not a live reference. |
| `test_second_write_to_same_field_supersedes_rather_than_merging` | The canon's explicit rule: a later write to the same sector. |
| `test_a_field_absent_from_the_write_is_preserved_not_cleared` | The "additive" half of the same rule: a write that doesn't touch. |
| `test_upsert_sector_always_restamps_last_seen_ts` | An EXPLICIT caller-supplied last_seen_ts is real content (a. |
| `test_write_from_state_class_unobserved_preserves_a_previously_cim_learned_class` | Adapted from mack's probe_clobber. |
| `test_upsert_sector_explicit_none_class_still_resets_it` | The nested merge only preserves ABSENT sub-keys -- a caller that. |
| `test_upsert_sector_explicit_none_port_still_resets_the_whole_field` | An explicit top-level `"port": None` (the whole field, not a. |
| `test_bulk_upsert_writes_many_sectors_in_one_pass` | Bulk upsert writes many sectors in one pass. |
| `test_bulk_upsert_empty_list_is_a_noop` | Bulk upsert empty list is a noop. |
| `test_bulk_upsert_acquires_one_lock_per_new_sector_not_a_shared_lock` | mack Finding 3b: a bulk write of N sectors must NOT hold one. |
| `test_all_sectors_returns_sorted_by_sector_id` | All sectors returns sorted by sector id. |
| `test_all_sectors_returns_copies_not_live_references` | All sectors returns copies not live references. |
| `test_query_filters_by_predicate` | Query filters by predicate. |
| `test_two_worlds_never_share_sector_data` | Two worlds never share sector data. |
| `test_two_worlds_persist_to_distinct_sector_directories` | Two worlds persist to distinct sector directories. |
| `test_write_from_state_with_no_sector_field_is_a_noop` | Write from state with no sector field is a noop. |
| `test_write_from_state_maps_sector_and_warps` | Write from state maps sector and warps. |
| `test_write_from_state_maps_port_commodities` | Write from state maps port commodities. |
| `test_write_from_state_without_port_key_preserves_previously_known_port` | Write from state without port key preserves previously known port. |
| `test_write_from_state_ports_none_clears_prior_flyby` | WO-TUI-CHAIN-25948-FALSE-PORT: explicit port=None clears stale flyby. |
| `test_write_from_state_actually_persists` | Write from state actually persists. |
| `test_upsert_sector_identical_content_still_writes_and_advances_last_seen_ts` | Adapted from mack's probe_ts_semantics. |
| `test_upsert_sector_changed_content_still_writes` | Upsert sector changed content still writes. |
| `test_write_from_state_repeated_identical_observation_still_advances_last_seen_ts` | The real hot-path shape: write_from_state() never supplies an. |
| `test_bulk_upsert_repeat_batch_still_writes_and_advances_timestamps` | Bulk upsert repeat batch still writes and advances timestamps. |
| `test_write_port_only_writes_commodities_to_the_explicit_sector` | Write port only writes commodities to the explicit sector. |
| `test_write_port_only_never_touches_warps_or_threats_for_the_sector` | A docked port visit observes nothing about warps/threats -- an. |
| `test_write_port_only_never_clobbers_a_previously_cim_learned_class` | Mirrors write_from_state's own mack-Finding-1 guarantee: a class. |
| `test_write_port_only_actually_persists` | Write port only actually persists. |
| `test_single_sector_upsert_cost_does_not_grow_with_total_known_sectors` | Adapted from mack's probe_hotpath. |
| `test_all_sectors_still_lists_every_sector_at_scale` | Sanity check alongside the hot-path proof above -- the O(1) write. |
| `test_sector_lock_real_flock_blocks_second_acquirer_until_released` | Real flock proof -- no monkeypatch, no threads: a second, wholly. |
| `test_concurrent_writes_to_different_sectors_do_not_serialize` | Adapted from mack's probe_contention. |
| `test_concurrent_upsert_to_the_same_sector_never_loses_an_update` | Same-sector concurrency still needs the lock for correctness --. |
| `test_real_concurrent_upsert_across_many_threads_never_loses_an_update` | The acceptance bar (mirrors player_bank's real-writer test): N. |
| `test_module_level_paths_are_under_the_real_gitignored_state_dir` | Sanity check on the constants themselves -- doesn't touch disk. |
| `test_write_from_state_flyby_presence_sets_port_without_wiping_commodities` | Presence-only flyby must not emit commodities=[] and clobber a prior docked read. |
| `test_write_from_state_flyby_empty_presence_creates_port` | Write from state flyby empty presence creates port. |
