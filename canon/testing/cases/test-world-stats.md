---
type: Reference
title: Test Cases — test_world_stats
description: WorldStats client overlay + world_model.known_sector_count (WO-GOALS-STATUS-VOCABULARY T1).
resource: repo://tw2002-aiclient/tests/test_world_stats.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-28T14:22:36Z
---

# Test Cases — `tests/test_world_stats.py`

_Unit behaviour behind the GOALS Map row's producer. The WIRE (that `_run_play`
calls `refresh`, against this profile's world, and that the number reaches the
closure GOALS polls) is pinned in `tests/test_play_chains_discovered.py`._

| Test | Blurb |
|------|-------|
| `test_it_counts_the_sector_files` | It counts the sector files. |
| `test_it_agrees_with_all_sectors` | The cheap count and the expensive list answer the same question. |
| `test_a_world_never_written_counts_zero` | Zero is a fact here, not a fabrication. |
| `test_lock_siblings_and_stray_files_are_not_counted` | `.json.lock` siblings and non-numeric `*.json` are skipped, not counted or raised on. |
| `test_it_does_not_read_the_files` | Unparseable content still counts — proof the count never opens them. |
| `test_an_unreadable_store_is_unknown_not_zero` | The load-bearing distinction, with a readable positive control on both sides. |
| `test_a_file_where_the_sectors_dir_should_be_is_unknown_not_zero` | A non-directory at the sectors path is unknown, not zero. |
| `test_it_contributes_nothing_before_a_refresh` | No world-model read happens unasked. |
| `test_a_refresh_supplies_the_count` | A refresh supplies the count. |
| `test_zero_is_supplied_not_swallowed` | A measured zero is reported, not turned back into "unknown" by a falsy check. |
| `test_it_never_mutates_the_status_it_is_given` | It never mutates the status it is given. |
| `test_a_supplied_value_wins` | A future daemon-side producer is never clobbered by this cache. |
| `test_a_supplied_none_is_filled_in` | An explicit `None` is filled in. |
| `test_junk_counts_are_refused` | `True` is an `int` and would render as "1 sectors"; junk and negatives are refused. |
| `test_a_raising_world_model_is_swallowed` | A raising world model is swallowed. |
| `test_a_failed_refresh_keeps_the_last_observed_count` | A later failure says nothing about the moment we measured. |
| `test_a_non_dict_status_passes_through_untouched` | A provider's own "no status" signal survives untouched. |
| `test_wrapping_none_stays_none` | An absent status source stays absent. |
| `test_wrap_overlays_any_provider` | Wrap overlays any provider. |
| `test_the_two_overlays_compose_in_either_order` | `app.py`'s nesting of the two overlays must not become load-bearing. |
