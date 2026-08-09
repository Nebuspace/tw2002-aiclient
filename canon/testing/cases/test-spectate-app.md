---
type: Reference
title: Test Cases — test_spectate_app
description: REMOVED — historical inventory for deleted ops `tw spectate` suite (tip: test_cockpit_spectate).
resource: repo://tw2002-aiclient/tests/test_spectate_app.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_spectate_app.py`

> **Tip reality:** `tests/test_spectate_app.py` and ops `tw spectate` / `spectate_app.py` are
> **REMOVED / RETIRED**. Live observation coverage is `tests/test_cockpit_spectate.py` (in-cockpit
> Spectate) plus `tw watch`. The table below is a **historical inventory** of the deleted suite —
> not a claim the module still ships.

_Regression test for the interactive `tw spectate` curses render path (historical)._

> **REMOVED** — module absent on tip (not merely pytest-ignored). Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_interactive_spectate_renders_frame_and_hud_under_a_real_pty` | Phase 0/1 regression -- the bordered viewport + HUD chrome must reach the real terminal, not just compose_hud_cells()'s pure output. |
| `test_interactive_spectate_renders_real_terminal_colors_under_a_real_pty` | D13: the viewport must render the game's actual ANSI colors via curses color pairs, not plain text. |
| `test_interactive_spectate_viewport_is_native_size_and_un_inset_under_a_fake_pty` | Interactive spectate viewport is native size and un inset under a fake pty. |
| `test_interactive_spectate_hud_persists_and_ages_freshness_under_a_fake_pty` | The HUD accumulator's full live payoff, end-to-end through real curses rendering (not just the pure unit tests in test_spectate_layout.py): 1. |
| `test_interactive_spectate_credit_gain_flashes_green_with_a_chip_under_a_fake_pty` | Phase 3 motion B1: a credits INCREASE flashes the HUD cell green with a floating "+230 ▲" chip. |
| `test_interactive_spectate_credit_loss_flashes_red_with_a_chip_under_a_fake_pty` | Phase 3 motion B1: a credits DECREASE flashes red with a "-500 ▼" chip. |
| `test_interactive_spectate_credits_sparkline_renders_under_a_fake_pty` | Interactive spectate credits sparkline renders under a fake pty. |
| `test_interactive_spectate_turns_gauge_renders_and_colors_danger_when_low_under_a_fake_pty` | Phase 4 motion C5: the turns-left fuel gauge bar-meter appears once a session-max is known, and colors red once the fraction drops into the danger band (<20%). |
| `test_interactive_spectate_port_panel_renders_bar_meters_under_a_fake_pty` | Phase 4 motion C4: port commodity %-bar-meters appear in the HUD gutter, colored green for a "buying" row. |
| `test_interactive_spectate_ticker_flashes_newest_row_under_a_fake_pty` | Phase 3 motion B3: the newest ticker row gets a brief highlighted color right after it arrives. |
| `test_interactive_spectate_classification_pulse_reverses_header_under_a_fake_pty` | Phase 3 motion B4: a classification CHANGE briefly reverses the header line. |
| `test_on_sigint_sets_detach_pending_flag` | TW-15 unit: SIGINT handler must arm the detach latch (the real-terminal path under curses cbreak/ISIG never delivers byte 3 to getch). |
| `test_sigint_detaches_interactive_spectate_under_a_fake_pty` | Sigint detaches interactive spectate under a fake pty. |
| `test_control_strip_shows_the_ai_pilot_badge_and_hints_under_a_fake_pty` | Control strip shows the ai pilot badge and hints under a fake pty. |
| `test_intervention_strip_paints_when_needs_attention_under_a_fake_pty` | WO-SPECTATE-INTERVENTION-STRIP: ops spectate surfaces halt without the product play TUI when status.intervention.needs_attention. |
| `test_intervention_strip_omitted_when_healthy_under_a_fake_pty` | Intervention strip omitted when healthy under a fake pty. |
| `test_control_strip_shows_the_attach_takeover_hint_under_a_fake_pty` | Control strip shows the attach takeover hint under a fake pty. |
| `test_control_strip_shows_the_auto_loop_badge_and_live_progress_bar_under_a_fake_pty` | Control strip shows the auto loop badge and live progress bar under a fake pty. |
| `test_control_strip_shows_manual_badge_when_a_human_is_attached_under_a_fake_pty` | Control strip shows manual badge when a human is attached under a fake pty. |
| `test_control_strip_shows_the_spectate_badge_and_survives_the_muted_tone_under_a_fake_pty` | Control strip shows the spectate badge and survives the muted tone under a fake pty. |
| `test_tone_attr_resolves_muted_and_degrades_gracefully_for_an_unknown_tone` | Tone attr resolves muted and degrades gracefully for an unknown tone. |
| `test_control_strip_shows_the_live_tx_readout_under_a_fake_pty` | Control strip shows the live tx readout under a fake pty. |
| `test_control_strip_ticker_pairs_tx_with_the_settle_outcome_under_a_fake_pty` | Control strip ticker pairs tx with the settle outcome under a fake pty. |
| `test_loops_library_overlay_opens_on_l_and_lists_loops_under_a_fake_pty` | Loops library overlay opens on l and lists loops under a fake pty. |
| `test_loops_library_overlay_closes_on_esc_and_dashboard_resumes_under_a_fake_pty` | Loops library overlay closes on esc and dashboard resumes under a fake pty. |
| `test_library_enter_arms_a_confirm_prompt_instead_of_launching_under_a_fake_pty` | Enter alone must never fire play_start -- it only ARMS the y/N gate. |
| `test_library_enter_then_y_fires_play_start_exactly_once_under_a_fake_pty` | Library enter then y fires play start exactly once under a fake pty. |
| `test_library_enter_then_cancel_sends_nothing_under_a_fake_pty` | Library enter then cancel sends nothing under a fake pty. |
| `test_status_identity_ignores_idle_age_and_clock_fields` | Regression: status polls change last_rx_age_s every time — that alone must NOT count as a chrome identity change (would re-dirty panes on every poll). |
| `test_idle_anim_interval_is_slower_than_connected` | Idle anim interval is slower than connected. |
| `test_spectate_source_status_poll_does_not_set_got_content` | Static guard: ordinary status polls must not assign got_content (the confirmed WO-SPECTATE-FLICKER mechanism). |
| `test_waiting_session_screen_mentions_no_game` | Waiting session screen mentions no game. |
| `test_outer_frame_only_drawn_when_got_content` | WO-SPECTATE-FLICKER mechanism #2: anim-only frames must NOT erase the full-client outer sibling (that blanks viewport/ticker). |
| `test_render_skips_outer_erase_on_anim_only_tick` | Runtime invariant: calm idle `_render` with got_content=False never calls `_draw_outer_frame` (no erase of the full-client sibling). |
| `test_fetch_status_passes_through_autopilot_trace` | Fetch status passes through autopilot trace. |
| `test_fetch_status_autopilot_trace_is_none_when_nothing_wired` | Fetch status autopilot trace is none when nothing wired. |
| `test_fetch_status_connect_failure_still_carries_the_key` | Fetch status connect failure still carries the key. |
| `test_fetch_status_passes_through_fa7a_credits` | WO-SPECTATE-HUD-SEED: status already serves FA7a credits; fetch_status must not drop them (same class of bug as autopilot_trace). |
| `test_spectate_seeds_hud_from_status_before_any_event_under_a_fake_pty` | Spectate seeds hud from status before any event under a fake pty. |
| `test_decisions_keeps_trace_never_goals_title` | Live autopilot_trace fills DECISIONS; GOALS never reclaim that pane. |
| `test_priorities_panel_owns_goals_with_chain_box` | GOALS render in PRIORITIES; DECISIONS stays trace-titled. |
| `test_decisions_idle_never_shows_tw13_stub` | With left PRIORITIES present and no explore/trace — honest idle, not TW-13. |
| `test_decisions_shows_coach_on_zero_fighters` | TW-13: 0 fighters → holds-first coaching card in DECISIONS. |
| `test_decisions_coach_does_not_override_live_trace` | Live autopilot_trace still owns DECISIONS over coach. |
| `test_decisions_midwidth_fallback_shows_priorities_when_no_left_gutter` | Without left PRIORITIES region, idle DECISIONS carries goals+weigh (not TW-13). |
| `test_decisions_keeps_explore_never_goals_title` | Explore mode owns DECISIONS; GOALS never reclaim that pane. |
| `test_decisions_pane_vanishes_below_its_height_floor_and_log_fills_the_band_under_a_fake_pty` | Pixel-flagged proof gap: the geometry floor (DECISIONS_MIN_H) was only proven at the pure frame_layout() level so far. |
| `test_longest_chain_for_panel_prefers_a_real_profit_chain` | A resolvable world_id with a discoverable profit cycle must win over the skill-library fallback -- the library's _send_control() must not even be consulted. |
| `test_longest_chain_for_panel_falls_back_when_world_id_missing` | Longest chain for panel falls back when world id missing. |
| `test_longest_chain_for_panel_falls_back_when_no_hops_discoverable` | Longest chain for panel falls back when no hops discoverable. |
| `test_longest_chain_for_panel_falls_back_when_hops_form_no_profitable_cycle` | Hops exist but don't close into a profitable cycle -- an honest fallback to the library, never a fabricated chain. |
| `test_presence_port_chain_seed_adjacent_ports` | Two adjacent flyby ports (class only, no commodities) → seed sectors. |
| `test_longest_chain_for_panel_seeds_when_library_empty` | No ProfitChain + empty library → presence seed (not empty placeholder). |
| `test_longest_chain_for_panel_seeds_when_library_lacks_sectors` | Live failure: list_skills rows have steps but no sectors — seed viz. |
| `test_presence_seed_prefers_current_sector_port` | Accept-3 LIVE: current sector on a presence-port path → that pair. |
| `test_presence_seed_grows_beyond_two_ports` | WO-TUI-CHAIN-VIZ-GROW: three contiguous presence ports → full path. |
| `test_presence_seed_requires_direct_port_warps` | Ports linked only through an empty sector do not seed a chain. |
| `test_compose_chain_bubbles_drops_non_port_when_known_ports_set` | Compose defense: non-port ids break contiguity — never bridge bubbles. |
| `test_presence_seed_four_contiguous_ports` | Four direct port→port warps → seed length 4. |
| `test_longest_chain_for_panel_skips_profit_chain_with_non_port` | ProfitChain with a non-port sector → presence contiguous seed instead. |
| `test_longest_chain_for_panel_still_prefers_profit_chain_over_seed` | Real ProfitCycle wins; presence seed must not be consulted. |
| `test_resolve_world_id_prefers_status_over_ambiguous_store` | Resolve world id prefers status over ambiguous store. |
| `test_resolve_world_id_matches_host_when_multiple_worlds` | Resolve world id matches host when multiple worlds. |
| `test_stamp_live_world_metrics_uses_status_world_id` | Stamp live world metrics uses status world id. |
| `test_suspend_and_run_attach_launches_tw_attach_and_restores_curses` | Suspend and run attach launches tw attach and restores curses. |
| `test_suspend_and_run_attach_reports_a_nonzero_exit_without_raising` | Suspend and run attach reports a nonzero exit without raising. |
| `test_suspend_and_run_attach_restores_curses_even_on_a_missing_binary` | Suspend and run attach restores curses even on a missing binary. |
| `test_handle_key_a_invokes_attach_and_records_the_error_on_status` | Handle key a invokes attach and records the error on status. |
| `test_handle_key_a_is_a_safe_noop_without_a_stdscr` | A caller that hasn't wired stdscr through (e.g. |
| `test_idle_prompt_overlay_enter_then_y_sends_do` | Idle prompt overlay enter then y sends do. |
| `test_blank_dashboard_windows_erases_each_pane` | Blank dashboard windows erases each pane. |
| `test_idle_prompt_overlay_secret_never_sends_do` | Idle prompt overlay secret never sends do. |
| `test_maybe_arm_idle_prompt_opens_after_threshold` | Maybe arm idle prompt opens after threshold. |
| `test_spectate_client_auto_reconnects_after_sock_recycle` | Spectate client auto reconnects after sock recycle. |
| `test_spectate_client_exhausts_reconnect_and_sets_flag` | Spectate client exhausts reconnect and sets flag. |
| `test_menu_map_summary_localizes_star_and_off_map` | Menu map summary localizes star and off map. |
| `test_render_paints_menu_map_here_star` | Render paints menu map here star. |
| `test_interactive_spectate_paints_menu_map_off_map_under_a_fake_pty` | Wide terminal allocates MENU MAP; no world store → honest off-map. |
