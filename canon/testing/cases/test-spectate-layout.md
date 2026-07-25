---
type: Reference
title: Test Cases — Spectate Layout
description: Spectator dashboard layout tests — pure functions, no curses/terminal.
resource: repo://tw2002-aiclient/tests/test_spectate_layout.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_spectate_layout.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Spectator dashboard layout tests — pure functions, no curses/terminal_

| Test | Blurb |
|------|-------|
| `test_sidebar_includes_classification_and_settled_reason` | Sidebar includes classification and settled reason. |
| `test_sidebar_includes_parsed_state_fields` | Sidebar includes parsed state fields. |
| `test_sidebar_prefers_turns_left_over_turn_timer_when_both_absent_is_fine` | Sidebar prefers turns left over turn timer when both absent is fine. |
| `test_sidebar_renders_port_commodities` | Sidebar renders port commodities. |
| `test_sidebar_omits_missing_fields_gracefully` | Sidebar omits missing fields gracefully. |
| `test_sidebar_renders_confidence_and_novelty_when_present` | Forward-compatible with a future A5 confidence/novelty score --. |
| `test_ticker_entry_format` | Ticker entry format. |
| `test_ticker_entry_truncates_long_prompts` | Ticker entry truncates long prompts. |
| `test_ticker_entry_pairs_the_sent_input_when_present` | Ticker entry pairs the sent input when present. |
| `test_ticker_entry_omits_tx_segment_when_absent` | Ticker entry omits tx segment when absent. |
| `test_ticker_history_pairs_sent_with_prior_prompt_not_landing` | WO-TUI-LOG-QA-SKEW: answer attaches to the prompt it answered. |
| `test_ticker_history_left_class_is_answered_not_landing` | WO-TUI-LOG-QA-LABELS: left class tag matches the prompt that got the answer. |
| `test_ticker_history_orphan_first_sent_does_not_false_pair` | First event with →sent and no prior must not claim landing was answered. |
| `test_status_line_connected` | Status line connected. |
| `test_status_line_disconnected_defaults` | Status line disconnected defaults. |
| `test_compose_dashboard_assembles_all_sections` | Compose dashboard assembles all sections. |
| `test_compose_dashboard_caps_ticker_to_max_recent` | Compose dashboard caps ticker to max recent. |
| `test_compose_dashboard_handles_no_event_yet` | Compose dashboard handles no event yet. |
| `test_compose_dashboard_carries_color_map_alongside_main_text` | D13: main_color rides alongside main so a curses renderer can zip. |
| `test_compose_dashboard_defaults_main_color_when_absent` | Compose dashboard defaults main color when absent. |
| `test_render_plain_includes_all_sections_and_is_a_single_string` | Render plain includes all sections and is a single string. |
| `test_render_plain_handles_empty_dashboard_without_crashing` | Render plain handles empty dashboard without crashing. |
| `test_frame_layout_below_floor_is_too_small` | Frame layout below floor is too small. |
| `test_frame_layout_no_border_tier_below_viewport_width` | Frame layout no border tier below viewport width. |
| `test_frame_layout_minimal_tier_borders_and_centers_with_no_gutter` | Frame layout minimal tier borders and centers with no gutter. |
| `test_frame_layout_right_gutter_tier_left_anchors_viewport` | Frame layout right gutter tier left anchors viewport. |
| `test_frame_layout_full_tier_centers_viewport_with_right_gutter` | Frame layout full tier centers viewport with right gutter. |
| `test_frame_layout_viewport_never_stretched_beyond_native_grid` | Frame layout viewport never stretched beyond native grid. |
| `test_frame_layout_status_bar_always_present_and_pinned_to_last_inner_row` | Frame layout status bar always present and pinned to last inner row. |
| `test_frame_layout_drops_header_before_border_under_height_pressure` | Exactly enough body height for a bordered viewport and nothing. |
| `test_frame_layout_adds_header_once_there_is_a_spare_line` | Frame layout adds header once there is a spare line. |
| `test_frame_layout_too_small_has_no_control_region` | Frame layout too small has no control region. |
| `test_frame_layout_control_strip_sits_directly_above_status_when_present` | Frame layout control strip sits directly above status when present. |
| `test_frame_layout_control_strip_takes_priority_over_ticker_for_scarce_leftover` | Exactly one spare body row (not enough for BOTH control and a. |
| `test_frame_layout_ticker_still_appears_with_enough_leftover_for_both` | Frame layout ticker still appears with enough leftover for both. |
| `test_frame_layout_is_a_pure_function_of_its_inputs` | Frame layout is a pure function of its inputs. |
| `test_frame_layout_tw08_regions_do_not_overlap_at_full_tier` | TW-08 geometry proof: outer / viewport / gutter / decisions /. |
| `test_update_tracked_stats_persists_fields_across_events_lacking_them` | The exact bug this replaces: format_sidebar's `if "credits" in. |
| `test_update_tracked_stats_updates_only_fields_present_on_the_new_event` | Update tracked stats updates only fields present on the new event. |
| `test_update_tracked_stats_prefers_turns_left_and_ignores_turn_timer` | Update tracked stats prefers turns left and ignores turn timer. |
| `test_update_tracked_stats_count_survives_later_timer_only_screen` | WO-TUI-HUD-POLISH / WO-TUI-HUD-TURNS-COUNT: TL= must not clobber turns. |
| `test_update_tracked_stats_timer_alone_leaves_turns_blank` | WO-TUI-HUD-TURNS-COUNT: TURNS slot is count-only — never HH:MM:SS. |
| `test_update_tracked_stats_prefers_fa7a_credits_and_ignores_port_quote_state` | FA7a top-level balance wins; loose state credits must not replace it. |
| `test_compose_hud_cells_credits_persist_when_absent_from_later_screen` | Compose hud cells credits persist when absent from later screen. |
| `test_hud_gutter_width_floor_fits_credits_freshness` | WO-TUI-HUD-POLISH: pin HUD_GUTTER_W ≥34 and tier floors stay coherent. |
| `test_update_tracked_stats_computes_profit_as_delta_from_first_seen_credits` | Update tracked stats computes profit as delta from first seen credits. |
| `test_seed_tracked_from_status_fills_fa7a_credits_on_cold_start` | Seed tracked from status fills fa7a credits on cold start. |
| `test_seed_tracked_from_status_backfills_missing_fields_without_clobbering` | Seed tracked from status backfills missing fields without clobbering. |
| `test_seed_tracked_from_status_uses_parsed_state_when_tracked_empty` | Seed tracked from status uses parsed state when tracked empty. |
| `test_seed_tracked_from_status_prefers_status_turns_left` | WO-HUD-CREDITS-TURNS-JOIN: sticky session turns via status beat a. |
| `test_update_tracked_stats_is_pure_returns_new_dict` | Update tracked stats is pure returns new dict. |
| `test_update_tracked_stats_handles_none_event` | Update tracked stats handles none event. |
| `test_format_freshness_shows_now_for_sub_second_age` | Format freshness shows now for sub second age. |
| `test_format_freshness_shows_seconds_ago` | Format freshness shows seconds ago. |
| `test_format_freshness_accepts_an_ascii_mark` | Format freshness accepts an ascii mark. |
| `test_compose_hud_cells_placeholder_shape_with_no_data_yet` | Compose hud cells placeholder shape with no data yet. |
| `test_compose_hud_cells_formats_values_and_freshness` | Compose hud cells formats values and freshness. |
| `test_compose_hud_cells_dims_a_cell_past_the_staleness_threshold` | Compose hud cells dims a cell past the staleness threshold. |
| `test_compose_hud_cells_turns_cell_ignores_live_timer` | Compose hud cells turns cell ignores live timer. |
| `test_compose_hud_cells_turns_cell_shows_comma_formatted_count` | Compose hud cells turns cell shows comma formatted count. |
| `test_compose_live_metrics_placeholder_shape` | Compose live metrics placeholder shape. |
| `test_compose_live_metrics_reads_tracked_tuple_values` | Compose live metrics reads tracked tuple values. |
| `test_aggregate_world_metrics_sectors_mapped_is_record_count` | Aggregate world metrics sectors mapped is record count. |
| `test_aggregate_world_metrics_counts_ports_threats_landmarks` | Aggregate world metrics counts ports threats landmarks. |
| `test_stamp_world_metrics_feeds_compose_live_metrics` | Stamp world metrics feeds compose live metrics. |
| `test_compute_autonomy_ratio_trainer_over_ai_plus_trainer` | Compute autonomy ratio trainer over ai plus trainer. |
| `test_compute_autonomy_ratio_empty_and_window` | Compute autonomy ratio empty and window. |
| `test_compute_autonomy_ratio_default_counts_entire_ledger` | PRIORITIES footer must climb forever — not a trailing 500-row window. |
| `test_format_autonomy_lines_ties_pct_to_app_ai_counts` | Format autonomy lines ties pct to app ai counts. |
| `test_format_autopilot_trace_lines_chosen_gated_and_hold` | Format autopilot trace lines chosen gated and hold. |
| `test_compose_hud_cells_appends_autonomy_when_provided` | Compose hud cells appends autonomy when provided. |
| `test_compose_primary_goals_fighters_line` | Compose primary goals fighters line. |
| `test_compose_primary_goals_fighters_buy_status_labels` | fighter_buy_status overrides 'need some' fallback when fighters count is zero. |
| `test_compose_primary_goals_ship_hold_prices_gated_without_stardock` | Compose primary goals ship hold prices gated without stardock. |
| `test_update_tracked_stats_records_fighters_aboard` | Update tracked stats records fighters aboard. |
| `test_compose_primary_goals_and_chain_highlight` | Compose primary goals and chain highlight. |
| `test_compose_priorities_lines_orders_by_ev_with_readable_labels` | Engine ranks ungated chain first; upgrade gated without payback. |
| `test_compose_priorities_lines_engine_stay_vs_leave_demotes_upgrade` | RT stay-vs-leave gates upgrade below chain even when raw EV is higher. |
| `test_compose_priorities_lines_empty_unknown_is_clear` | Compose priorities lines empty unknown is clear. |
| `test_compose_priorities_panel_folds_goals_and_weigh_list` | Left gutter: GOALS + FOCUS + autonomy footer box — never in DECISIONS. |
| `test_compose_autonomy_footer_box_centers_and_fits_width` | Compose autonomy footer box centers and fits width. |
| `test_compose_menu_map_panel_here_star_and_off_map` | WO-FA8: spectate MENU MAP lines reuse menu_map_view clip-safe format. |
| `test_compose_formations_panel_lists_name_and_blurb` | Compose formations panel lists name and blurb. |
| `test_compose_formations_panel_truncates_with_more` | Compose formations panel truncates with more. |
| `test_compose_formations_panel_groups_same_kind` | Compose formations panel groups same kind. |
| `test_compose_phase2_side_panel_does_not_fold_priorities` | PRIORITIES is its own TUI box — never a section inside GOALS. |
| `test_frame_layout_full_tier_priorities_matches_hud_width` | WO-TUI-PRIORITIES-LEFT: full tier PRIORITIES width == HUD_GUTTER_W. |
| `test_frame_layout_decisions_hud_aligned_in_right_column` | WO-TUI-DECISIONS-HUD-ALIGN: DECISIONS width matches HUD; bottom aligns. |
| `test_frame_layout_hud_keeps_room_for_metrics` | Decisions-in-HUD must not clip METRICS (HUD_GUTTER_MIN_H=10 regression). |
| `test_frame_layout_left_priorities_absent_below_left_gutter_floor` | Right HUD alone (118) — no left PRIORITIES until LEFT_GUTTER_MIN_COLS. |
| `test_chain_hop_count_and_unit_object_chain_is_always_hops` | Chain hop count and unit object chain is always hops. |
| `test_chain_hop_count_and_unit_recorded_or_mined_dict_is_steps` | Chain hop count and unit recorded or mined dict is steps. |
| `test_chain_hop_count_and_unit_discovered_dict_is_hops` | Chain hop count and unit discovered dict is hops. |
| `test_chain_hop_count_and_unit_none_chain` | Chain hop count and unit none chain. |
| `test_chain_hop_count_and_unit_presence_seed_from_sectors` | Presence-seed viz has sectors but historically omitted steps — GOALS. |
| `test_compose_primary_goals_presence_seed_not_none_yet` | Compose primary goals presence seed not none yet. |
| `test_compose_primary_goals_lines_labels_steps_vs_hops` | Compose primary goals lines labels steps vs hops. |
| `test_format_chain_summary_dict_branch_labels_steps_vs_hops` | Format chain summary dict branch labels steps vs hops. |
| `test_format_chain_summary_non_numeric_sector_does_not_crash_the_membership_check` | Pixel-caught defect (pre-existing, in a function this WO touched):. |
| `test_decisions_should_show_chain_dwell_window_and_wraps` | Decisions should show chain dwell window and wraps. |
| `test_frame_layout_decisions_absent_below_its_height_floor` | Just enough leftover for a bare LOG box (LOG_BOX_MIN_H) but short of. |
| `test_frame_layout_decisions_present_at_its_height_floor` | Frame layout decisions present at its height floor. |
| `test_frame_layout_band_grows_toward_double_height` | WO-TUI-CHAIN-BOX: band_h targets min(10, leftover) so LOG/DECISIONS. |
| `test_render_plain_includes_phase2_sections` | Render plain includes phase2 sections. |
| `test_compose_decisions_placeholder_is_nonempty_honest_idle` | Compose decisions placeholder is nonempty honest idle. |
| `test_infer_coach_triggers_maps_context_to_existing_when_triggers` | Infer coach triggers maps context to existing when triggers. |
| `test_compose_decisions_coach_trigger_and_empty` | Compose decisions coach trigger and empty. |
| `test_tick_down_timer_counts_down_and_floors_at_zero` | Tick down timer counts down and floors at zero. |
| `test_tick_down_timer_passes_through_unparseable_input` | Tick down timer passes through unparseable input. |
| `test_format_idle_age_seconds_then_minutes` | Format idle age seconds then minutes. |
| `test_status_semantic_disconnected_is_danger` | Status semantic disconnected is danger. |
| `test_status_semantic_connected_and_fresh_is_ok` | Status semantic connected and fresh is ok. |
| `test_status_semantic_connected_but_stale_rx_is_warn` | Status semantic connected but stale rx is warn. |
| `test_is_recent_true_within_window_false_after_and_for_none` | Is recent true within window false after and for none. |
| `test_render_bar_meter_scales_and_clamps` | Render bar meter scales and clamps. |
| `test_render_bar_meter_accepts_ascii_fallback_chars` | Render bar meter accepts ascii fallback chars. |
| `test_render_sparkline_empty_series_is_empty_string` | Render sparkline empty series is empty string. |
| `test_render_sparkline_flat_series_uses_middle_glyph` | Render sparkline flat series uses middle glyph. |
| `test_render_sparkline_scales_to_series_min_max` | Render sparkline scales to series min max. |
| `test_gauge_semantic_thresholds` | Gauge semantic thresholds. |
| `test_update_tracked_stats_sets_ticker_flash_on_any_real_event` | Update tracked stats sets ticker flash on any real event. |
| `test_update_tracked_stats_does_not_set_ticker_flash_for_a_none_event` | Update tracked stats does not set ticker flash for a none event. |
| `test_update_tracked_stats_pulses_on_classification_change_only` | Update tracked stats pulses on classification change only. |
| `test_update_tracked_stats_flashes_and_tweens_on_a_real_credits_change` | Update tracked stats flashes and tweens on a real credits change. |
| `test_update_tracked_stats_does_not_flash_when_credits_is_unchanged` | Update tracked stats does not flash when credits is unchanged. |
| `test_update_tracked_stats_builds_a_bounded_credit_series` | Update tracked stats builds a bounded credit series. |
| `test_update_tracked_stats_turns_max_tracks_the_session_high` | Update tracked stats turns max tracks the session high. |
| `test_credits_cell_flashes_gain_with_a_chip_and_tweens_toward_the_target` | Credits cell flashes gain with a chip and tweens toward the target. |
| `test_credits_cell_flashes_loss_on_a_decrease` | Credits cell flashes loss on a decrease. |
| `test_credits_cell_no_flash_or_chip_on_first_sighting` | Credits cell no flash or chip on first sighting. |
| `test_credits_cell_carries_a_sparkline_once_there_is_a_series` | Credits cell carries a sparkline once there is a series. |
| `test_turns_cell_shows_a_gauge_and_tone_once_a_max_is_known` | Turns cell shows a gauge and tone once a max is known. |
| `test_turns_cell_legacy_timer_entry_renders_blank_not_hhmmss` | Pre-count-only tracked shape must not paint HH:MM:SS into TURNS. |
| `test_non_credits_non_turns_cells_carry_neutral_extras` | Non credits non turns cells carry neutral extras. |
| `test_compose_port_panel_empty_when_no_port_in_state` | Compose port panel empty when no port in state. |
| `test_compose_port_panel_renders_one_row_per_commodity_with_bar_and_tone` | Compose port panel renders one row per commodity with bar and tone. |
| `test_compose_port_panel_does_not_persist_across_events` | Deliberate design choice (see compose_port_panel's docstring): a. |
| `test_format_mode_badge_known_modes` | Format mode badge known modes. |
| `test_format_mode_badge_unknown_mode_degrades_gracefully` | Format mode badge unknown mode degrades gracefully. |
| `test_format_mode_badge_handles_falsy_mode` | Format mode badge handles falsy mode. |
| `test_format_tx_readout_shows_dash_when_nothing_sent_yet` | Format tx readout shows dash when nothing sent yet. |
| `test_format_tx_readout_shows_the_sent_text` | Format tx readout shows the sent text. |
| `test_format_play_progress_or_hints_shows_hints_when_nothing_running` | Format play progress or hints shows hints when nothing running. |
| `test_format_play_progress_or_hints_shows_a_live_bar_while_running` | Format play progress or hints shows a live bar while running. |
| `test_format_play_progress_or_hints_shows_paused_state` | Format play progress or hints shows paused state. |
| `test_format_play_progress_or_hints_guards_zero_cycles_total` | Format play progress or hints guards zero cycles total. |
| `test_compose_control_strip_assembles_all_segments` | Compose control strip assembles all segments. |
| `test_compose_control_strip_shows_hints_when_idle` | Compose control strip shows hints when idle. |
| `test_compose_intervention_strip_omits_when_healthy` | Compose intervention strip omits when healthy. |
| `test_compose_intervention_strip_paints_when_needs_attention` | Compose intervention strip paints when needs attention. |
| `test_frame_layout_allocates_intervention_row_only_when_attention` | Frame layout allocates intervention row only when attention. |
| `test_control_hints_points_to_tw_attach_for_human_takeover` | Human-reported discoverability gap: `M` only cycles ai_pilot<->. |
| `test_format_loops_library_row_mined_shows_three_metrics` | Format loops library row mined shows three metrics. |
| `test_format_loops_library_row_recorded_shows_overall_and_exec` | Format loops library row recorded shows overall and exec. |
| `test_format_loops_library_row_no_profit_data_shows_dash` | Format loops library row no profit data shows dash. |
| `test_format_loops_library_row_discovered_shows_hops` | A genuine discovered trade-loop chain (chains. |
| `test_format_loops_library_row_selected_gets_a_marker` | Format loops library row selected gets a marker. |
| `test_format_loops_library_row_longest_gets_star` | Format loops library row longest gets star. |
| `test_format_loops_library_row_truncates_to_cols` | Format loops library row truncates to cols. |
| `test_format_loops_library_header_shows_count_and_tw07_title` | Format loops library header shows count and tw07 title. |
| `test_sort_trade_loop_chains_profit_desc` | Sort trade loop chains profit desc. |
| `test_longest_chain_steps_and_banner` | Longest chain steps and banner. |
| `test_longest_chain_banner_discovered_shows_hops` | Longest chain banner discovered shows hops. |
| `test_compose_chain_bubbles_empty_is_quiet_placeholder` | Compose chain bubbles empty is quiet placeholder. |
| `test_compose_chain_bubbles_two_hop_accept_contract` | Hub Accept visual contract (2-hop, ship at 100, classes known). |
| `test_compose_chain_bubbles_grows_with_hop_count` | Compose chain bubbles grows with hop count. |
| `test_longest_contiguous_port_run_splits_at_non_port` | Longest contiguous port run splits at non port. |
| `test_compose_chain_bubbles_contiguous_port_run_only` | Non-port breaks chain; bubbles never bridge across empty warps. |
| `test_compose_chain_bubbles_unknown_class_is_question_mark` | Compose chain bubbles unknown class is question mark. |
| `test_idle_prompt_should_offer_ai_pilot_blocking_after_threshold` | Idle prompt should offer ai pilot blocking after threshold. |
