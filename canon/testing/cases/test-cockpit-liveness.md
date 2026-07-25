---
type: Reference
title: Test Cases — test_cockpit_liveness
description: Pure liveness-cluster composer tests (WO-P3-038, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_liveness.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_liveness.py`

_Pure liveness-cluster composer tests (WO-P3-038, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_heartbeat_period_is_point_eight` | Heartbeat period is point eight. |
| `test_heartbeat_phase_boundaries` | Heartbeat phase boundaries. |
| `test_heartbeat_second_full_cycle_matches_first` | Heartbeat second full cycle matches first. |
| `test_heartbeat_never_raises_on_hostile_now_and_reads_phase_zero` | Heartbeat never raises on hostile now and reads phase zero. |
| `test_heartbeat_negative_now_clamps_to_phase_zero` | Heartbeat negative now clamps to phase zero. |
| `test_heartbeat_negative_now_just_past_boundary_still_clamps` | Heartbeat negative now just past boundary still clamps. |
| `test_heartbeat_raising_float_dunder_never_raises` | Heartbeat raising float dunder never raises. |
| `test_heartbeat_huge_int_never_raises` | Heartbeat huge int never raises. |
| `test_heartbeat_bool_input_coerces_like_a_number_not_raise` | Heartbeat bool input coerces like a number not raise. |
| `test_spinner_none_is_calm_frame_zero` | Spinner none is calm frame zero. |
| `test_spinner_default_arg_is_calm` | Spinner default arg is calm. |
| `test_spinner_valid_int_indexes_ramp` | Spinner valid int indexes ramp. |
| `test_spinner_ascii_ramp_indexing` | Spinner ascii ramp indexing. |
| `test_spinner_int_wraps_modulo_ramp_length` | Spinner int wraps modulo ramp length. |
| `test_spinner_negative_int_is_a_valid_wrapped_index` | Spinner negative int is a valid wrapped index. |
| `test_spinner_huge_int_never_raises_and_indexes` | Spinner huge int never raises and indexes. |
| `test_spinner_non_int_frame_falls_back_to_calm` | Spinner non int frame falls back to calm. |
| `test_spinner_bool_frame_never_renders_as_a_number` | Spinner bool frame never renders as a number. |
| `test_spinner_hostile_mod_dunder_never_raises` | Spinner hostile mod dunder never raises. |
| `test_tx_status_none_is_idle` | Tx status none is idle. |
| `test_tx_status_missing_tx_key_is_idle` | Tx status missing tx key is idle. |
| `test_tx_status_tx_not_a_dict_is_idle` | Tx status tx not a dict is idle. |
| `test_tx_sent_count_none_is_idle` | Tx sent count none is idle. |
| `test_tx_sent_count_missing_key_is_idle` | Tx sent count missing key is idle. |
| `test_tx_sent_count_zero_is_idle_matches_archive_falsy_check` | Tx sent count zero is idle matches archive falsy check. |
| `test_tx_sent_count_positive_int_renders` | Tx sent count positive int renders. |
| `test_tx_sent_count_whole_valued_float_renders_as_int` | Tx sent count whole valued float renders as int. |
| `test_tx_sent_count_fractional_float_is_idle` | Tx sent count fractional float is idle. |
| `test_tx_sent_count_non_finite_float_is_idle` | Tx sent count non finite float is idle. |
| `test_tx_sent_count_negative_is_idle` | Tx sent count negative is idle. |
| `test_tx_sent_count_bool_never_renders_as_a_number` | Tx sent count bool never renders as a number. |
| `test_tx_sent_count_string_is_idle_not_reparsed` | Tx sent count string is idle not reparsed. |
| `test_tx_sent_count_huge_int_never_raises_and_renders` | Tx sent count huge int never raises and renders. |
| `test_tx_extra_age_s_field_is_accepted_and_ignored` | Tx extra age s field is accepted and ignored. |
| `test_tx_non_dict_status_never_raises_and_is_idle` | Tx non dict status never raises and is idle. |
| `test_tx_hostile_dict_subclass_tx_slot_get_is_contained` | Tx hostile dict subclass tx slot get is contained. |
| `test_tx_arrow_glyph_never_swaps_when_idle` | Tx arrow glyph never swaps when idle. |
| `test_tx_arrow_glyph_never_swaps_when_sent` | Tx arrow glyph never swaps when sent. |
| `test_cluster_ordering_is_heartbeat_spinner_tx_space_separated` | Cluster ordering is heartbeat spinner tx space separated. |
| `test_cluster_ordering_stable_across_states` | Cluster ordering stable across states. |
| `test_cluster_ascii_mode_arrow_never_swaps_while_glyphs_do` | Cluster ascii mode arrow never swaps while glyphs do. |
| `test_cluster_none_status_degrades_every_field_independently` | Cluster none status degrades every field independently. |
| `test_cluster_hostile_status_never_raises` | Cluster hostile status never raises. |
| `test_cluster_width_clip_trims_line` | Cluster width clip trims line. |
| `test_cluster_width_zero_or_negative_empties_line` | Cluster width zero or negative empties line. |
| `test_cluster_width_non_int_never_raises_and_empties` | Cluster width non int never raises and empties. |
| `test_cluster_width_overflow_error_never_raises_and_empties` | Cluster width overflow error never raises and empties. |
| `test_cluster_hostile_now_never_raises` | Cluster hostile now never raises. |
| `test_cluster_spinner_frame_missing_key_is_calm` | Cluster spinner frame missing key is calm. |
| `test_cluster_non_int_spinner_frame_is_calm` | Cluster non int spinner frame is calm. |
| `test_heartbeat_glyph_never_raises_sweep` | Heartbeat glyph never raises sweep. |
| `test_spinner_glyph_never_raises_sweep` | Spinner glyph never raises sweep. |
| `test_format_tx_readout_never_raises_sweep` | Format tx readout never raises sweep. |
| `test_compose_liveness_cluster_never_raises_sweep` | Compose liveness cluster never raises sweep. |
