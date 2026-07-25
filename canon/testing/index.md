# testing/

OKF index for the `canon/testing/` bundle — pytest test case inventory for tw2002-aiclient.

- [Test Case Catalog](/testing/test-case-catalog.md) — Complete inventory of every pytest case (2271 tests · 129 modules), grouped by subsystem.

## Case Files (one per module)

### Cockpit & UI

- [test_cockpit_arm.py](/testing/cases/test-cockpit-arm.md) — 22 tests
- [test_cockpit_arm_pty.py](/testing/cases/test-cockpit-arm-pty.md) — 5 tests
- [test_cockpit_arm_wiring.py](/testing/cases/test-cockpit-arm-wiring.md) — 26 tests
- [test_cockpit_attach.py](/testing/cases/test-cockpit-attach.md) — 26 tests
- [test_cockpit_decisions.py](/testing/cases/test-cockpit-decisions.md) — 36 tests
- [test_cockpit_decisions_pty.py](/testing/cases/test-cockpit-decisions-pty.md) — 7 tests
- [test_cockpit_draw_runs.py](/testing/cases/test-cockpit-draw-runs.md) — 26 tests
- [test_cockpit_focus.py](/testing/cases/test-cockpit-focus.md) — 32 tests
- [test_cockpit_focus_pty.py](/testing/cases/test-cockpit-focus-pty.md) — 7 tests
- [test_cockpit_fold.py](/testing/cases/test-cockpit-fold.md) — 18 tests
- [test_cockpit_fold_pty.py](/testing/cases/test-cockpit-fold-pty.md) — 8 tests
- [test_cockpit_frame_pty.py](/testing/cases/test-cockpit-frame-pty.md) — 15 tests
- [test_cockpit_goals.py](/testing/cases/test-cockpit-goals.md) — 30 tests
- [test_cockpit_goals_pty.py](/testing/cases/test-cockpit-goals-pty.md) — 6 tests
- [test_cockpit_hud.py](/testing/cases/test-cockpit-hud.md) — 52 tests
- [test_cockpit_hud_pty.py](/testing/cases/test-cockpit-hud-pty.md) — 12 tests
- [test_cockpit_layout.py](/testing/cases/test-cockpit-layout.md) — 39 tests
- [test_cockpit_liveness.py](/testing/cases/test-cockpit-liveness.md) — 54 tests
- [test_cockpit_liveness_pty.py](/testing/cases/test-cockpit-liveness-pty.md) — 9 tests
- [test_cockpit_logsband.py](/testing/cases/test-cockpit-logsband.md) — 47 tests
- [test_cockpit_logsband_pty.py](/testing/cases/test-cockpit-logsband-pty.md) — 14 tests
- [test_cockpit_mode_badge.py](/testing/cases/test-cockpit-mode-badge.md) — 15 tests
- [test_cockpit_spectate.py](/testing/cases/test-cockpit-spectate.md) — 69 tests
- [test_cockpit_stopbanner.py](/testing/cases/test-cockpit-stopbanner.md) — 28 tests
- [test_cockpit_stopbanner_wiring.py](/testing/cases/test-cockpit-stopbanner-wiring.md) — 17 tests
- [test_cockpit_strip.py](/testing/cases/test-cockpit-strip.md) — 30 tests
- [test_cockpit_tones.py](/testing/cases/test-cockpit-tones.md) — 34 tests
- [test_cockpit_tones_pty.py](/testing/cases/test-cockpit-tones-pty.md) — 19 tests
- [test_cockpit_viewport.py](/testing/cases/test-cockpit-viewport.md) — 2 tests
- [test_cockpit_viewport_color.py](/testing/cases/test-cockpit-viewport-color.md) — 23 tests
- [test_cockpit_viewport_paint.py](/testing/cases/test-cockpit-viewport-paint.md) — 17 tests
- [test_cockpit_viewport_paint_color.py](/testing/cases/test-cockpit-viewport-paint-color.md) — 5 tests
- [test_cockpit_viewport_paint_pty.py](/testing/cases/test-cockpit-viewport-paint-pty.md) — 8 tests
- [test_cockpit_viewport_pty.py](/testing/cases/test-cockpit-viewport-pty.md) — 10 tests

### CLI Verbs & Entry Points

- [test_cli_attach_interactive_send_failure.py](/testing/cases/test-cli-attach-interactive-send-failure.md) — 8 tests
- [test_cli_attach_keys_exit_code.py](/testing/cases/test-cli-attach-keys-exit-code.md) — 3 tests
- [test_cli_crawl_wiring.py](/testing/cases/test-cli-crawl-wiring.md) — 3 tests _(BANKED)_
- [test_cli_haggle_wiring.py](/testing/cases/test-cli-haggle-wiring.md) — 2 tests _(BANKED)_
- [test_cli_log.py](/testing/cases/test-cli-log.md) — 3 tests
- [test_cli_menumap.py](/testing/cases/test-cli-menumap.md) — 7 tests
- [test_cli_ops_verb_a.py](/testing/cases/test-cli-ops-verb-a.md) — 7 tests
- [test_cli_ops_verb_b.py](/testing/cases/test-cli-ops-verb-b.md) — 7 tests
- [test_cli_ops_verb_c.py](/testing/cases/test-cli-ops-verb-c.md) — 4 tests
- [test_cli_ops_verb_e2.py](/testing/cases/test-cli-ops-verb-e2.md) — 3 tests
- [test_cli_players.py](/testing/cases/test-cli-players.md) — 20 tests _(BANKED)_
- [test_cli_run_dir.py](/testing/cases/test-cli-run-dir.md) — 12 tests

### Menu Map & Navigation

- [test_menu_crawler.py](/testing/cases/test-menu-crawler.md) — 63 tests _(BANKED)_
- [test_menu_map_view.py](/testing/cases/test-menu-map-view.md) — 9 tests
- [test_menu_nav.py](/testing/cases/test-menu-nav.md) — 9 tests
- [test_menu_sig.py](/testing/cases/test-menu-sig.md) — 5 tests

### Attach Protocol

- [test_attach_client_timeouts.py](/testing/cases/test-attach-client-timeouts.md) — 5 tests
- [test_attach_protocol.py](/testing/cases/test-attach-protocol.md) — 7 tests
- [test_attach_redaction.py](/testing/cases/test-attach-redaction.md) — 8 tests

### Spectate

- [test_spectate_app.py](/testing/cases/test-spectate-app.md) — 78 tests _(BANKED)_
- [test_spectate_layout.py](/testing/cases/test-spectate-layout.md) — 170 tests _(BANKED)_
- [test_spectate_no_send.py](/testing/cases/test-spectate-no-send.md) — 13 tests

### World Model & Identity

- [test_world_identity.py](/testing/cases/test-world-identity.md) — 13 tests _(BANKED)_
- [test_world_model.py](/testing/cases/test-world-model.md) — 53 tests _(BANKED)_
- [test_world_model_integration.py](/testing/cases/test-world-model-integration.md) — 21 tests _(BANKED)_

### Game Data & Knowledge

- [test_game_data.py](/testing/cases/test-game-data.md) — 5 tests _(BANKED)_
- [test_game_data_persist.py](/testing/cases/test-game-data-persist.md) — 25 tests _(BANKED)_
- [test_game_knowledge.py](/testing/cases/test-game-knowledge.md) — 43 tests _(BANKED)_
- [test_game_knowledge_learned_rules.py](/testing/cases/test-game-knowledge-learned-rules.md) — 6 tests _(BANKED)_

### Protocol

- [test_protocol_build_response_color.py](/testing/cases/test-protocol-build-response-color.md) — 11 tests
- [test_protocol_haggle.py](/testing/cases/test-protocol-haggle.md) — 6 tests _(BANKED)_
- [test_protocol_trainer_panel.py](/testing/cases/test-protocol-trainer-panel.md) — 31 tests _(BANKED)_

### Engine, Session & Utilities

- [test_actor_attribution.py](/testing/cases/test-actor-attribution.md) — 9 tests
- [test_aiclient_adapters.py](/testing/cases/test-aiclient-adapters.md) — 24 tests _(BANKED)_
- [test_aiclient_play_panels.py](/testing/cases/test-aiclient-play-panels.md) — 8 tests _(BANKED)_
- [test_analyze.py](/testing/cases/test-analyze.md) — 5 tests _(BANKED)_
- [test_chains.py](/testing/cases/test-chains.md) — 6 tests _(BANKED)_
- [test_classify.py](/testing/cases/test-classify.md) — 53 tests
- [test_clean_preempt.py](/testing/cases/test-clean-preempt.md) — 11 tests _(BANKED)_
- [test_connection.py](/testing/cases/test-connection.md) — 7 tests
- [test_control_lock.py](/testing/cases/test-control-lock.md) — 37 tests
- [test_control_panel.py](/testing/cases/test-control-panel.md) — 6 tests _(BANKED)_
- [test_crawl_driver.py](/testing/cases/test-crawl-driver.md) — 25 tests _(BANKED)_
- [test_crawl_start_protocol.py](/testing/cases/test-crawl-start-protocol.md) — 6 tests _(BANKED)_
- [test_credentials.py](/testing/cases/test-credentials.md) — 28 tests _(BANKED)_
- [test_ensure_from_play.py](/testing/cases/test-ensure-from-play.md) — 2 tests
- [test_ensure_no_auto_arm.py](/testing/cases/test-ensure-no-auto-arm.md) — 6 tests
- [test_ensure_protocol.py](/testing/cases/test-ensure-protocol.md) — 6 tests
- [test_env.py](/testing/cases/test-env.md) — 21 tests
- [test_explore.py](/testing/cases/test-explore.md) — 18 tests _(BANKED)_
- [test_fighter_toll_policy.py](/testing/cases/test-fighter-toll-policy.md) — 16 tests _(BANKED)_
- [test_formations.py](/testing/cases/test-formations.md) — 6 tests _(BANKED)_
- [test_frame_recorder.py](/testing/cases/test-frame-recorder.md) — 5 tests _(BANKED)_
- [test_glyph_table_dedupe.py](/testing/cases/test-glyph-table-dedupe.md) — 8 tests
- [test_guardian.py](/testing/cases/test-guardian.md) — 16 tests
- [test_haggle.py](/testing/cases/test-haggle.md) — 16 tests _(BANKED)_
- [test_hud_seed.py](/testing/cases/test-hud-seed.md) — 3 tests _(BANKED)_
- [test_iac.py](/testing/cases/test-iac.md) — 12 tests
- [test_integration_introspect_persist.py](/testing/cases/test-integration-introspect-persist.md) — 3 tests _(BANKED)_
- [test_interactive_app.py](/testing/cases/test-interactive-app.md) — 5 tests _(BANKED)_
- [test_intervention_labels.py](/testing/cases/test-intervention-labels.md) — 3 tests _(BANKED)_
- [test_introspector.py](/testing/cases/test-introspector.md) — 19 tests _(BANKED)_
- [test_ledger.py](/testing/cases/test-ledger.md) — 31 tests _(BANKED)_
- [test_logging_util.py](/testing/cases/test-logging-util.md) — 5 tests
- [test_login.py](/testing/cases/test-login.md) — 5 tests
- [test_login_redaction.py](/testing/cases/test-login-redaction.md) — 13 tests _(BANKED)_
- [test_login_resume.py](/testing/cases/test-login-resume.md) — 4 tests
- [test_miner.py](/testing/cases/test-miner.md) — 12 tests _(BANKED)_
- [test_mode_badge_vocabulary.py](/testing/cases/test-mode-badge-vocabulary.md) — 9 tests
- [test_name_bank.py](/testing/cases/test-name-bank.md) — 11 tests _(BANKED)_
- [test_play_chrome_nav.py](/testing/cases/test-play-chrome-nav.md) — 4 tests
- [test_play_esc_daemon_survival.py](/testing/cases/test-play-esc-daemon-survival.md) — 3 tests
- [test_player_bank.py](/testing/cases/test-player-bank.md) — 8 tests
- [test_probe.py](/testing/cases/test-probe.md) — 12 tests _(BANKED)_
- [test_profile_resolver.py](/testing/cases/test-profile-resolver.md) — 10 tests
- [test_pty_helpers.py](/testing/cases/test-pty-helpers.md) — 7 tests
- [test_pty_helpers_smoke.py](/testing/cases/test-pty-helpers-smoke.md) — 6 tests
- [test_replay_ledger_integration.py](/testing/cases/test-replay-ledger-integration.md) — 4 tests _(BANKED)_
- [test_safe_addstr_choke.py](/testing/cases/test-safe-addstr-choke.md) — 8 tests
- [test_screens_shared_pairs.py](/testing/cases/test-screens-shared-pairs.md) — 15 tests
- [test_servers.py](/testing/cases/test-servers.md) — 7 tests _(BANKED)_
- [test_session.py](/testing/cases/test-session.md) — 16 tests
- [test_settle.py](/testing/cases/test-settle.md) — 25 tests
- [test_ship_upgrade_decision.py](/testing/cases/test-ship-upgrade-decision.md) — 10 tests _(BANKED)_
- [test_skills.py](/testing/cases/test-skills.md) — 50 tests _(BANKED)_
- [test_state_parser.py](/testing/cases/test-state-parser.md) — 62 tests _(BANKED)_
- [test_terminal.py](/testing/cases/test-terminal.md) — 19 tests
- [test_trade_adapter.py](/testing/cases/test-trade-adapter.md) — 28 tests _(BANKED)_
- [test_trade_driver.py](/testing/cases/test-trade-driver.md) — 16 tests _(BANKED)_
- [test_transcript_tail.py](/testing/cases/test-transcript-tail.md) — 14 tests
- [test_tw04_toctou.py](/testing/cases/test-tw04-toctou.md) — 7 tests
- [test_unicode_ok_delegation.py](/testing/cases/test-unicode-ok-delegation.md) — 3 tests
- [test_watch.py](/testing/cases/test-watch.md) — 14 tests
- [test_watchfeed.py](/testing/cases/test-watchfeed.md) — 10 tests
- [test_watchfeed_wire.py](/testing/cases/test-watchfeed-wire.md) — 5 tests

