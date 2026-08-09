# Testing

OKF inventory of the pytest suite.

* [Test Case Catalog](/testing/test-case-catalog.md) — Inventory of every pytest case (2271 tests · 129 modules): one-sentence blurb per test; BANKED modules annotated.

## Per-module case files

* [test_actor_attribution.py](/testing/cases/test-actor-attribution.md) — Actor attribution at the send choke point (WO-P2-025).
* [test_aiclient_adapters.py](/testing/cases/test-aiclient-adapters.md) — Unit tests for tw2002_aiclient ensure/autopilot adapters (mocked daemon). _(BANKED)_
* [test_aiclient_play_panels.py](/testing/cases/test-aiclient-play-panels.md) — Aiclient play panels. _(BANKED)_
* [test_analyze.py](/testing/cases/test-analyze.md) — TW-12 session-retro analyzer tests — no network, synthetic ledger only. _(BANKED)_
* [test_attach_client_timeouts.py](/testing/cases/test-attach-client-timeouts.md) — AttachInputConn socket-op timeouts (HARDEN-ATTACH).
* [test_attach_protocol.py](/testing/cases/test-attach-protocol.md) — Attach control-lock handoff over a real unix socket + FakeAttachSession.
* [test_attach_redaction.py](/testing/cases/test-attach-redaction.md) — Attach keystroke secret redaction (WO-P2-OPS-VERB-F1b).
* [test_chains.py](/testing/cases/test-chains.md) — TW-21 longest-profit-chain algorithm tests (synthetic graphs). _(BANKED)_
* [test_classify.py](/testing/cases/test-classify.md) — Classify.
* [test_clean_preempt.py](/testing/cases/test-clean-preempt.md) — Clean preempt. _(BANKED)_
* [test_cli_attach_interactive_send_failure.py](/testing/cases/test-cli-attach-interactive-send-failure.md) — Cli attach interactive send failure.
* [test_cli_attach_keys_exit_code.py](/testing/cases/test-cli-attach-keys-exit-code.md) — Cli attach keys exit code.
* [test_cli_crawl_wiring.py](/testing/cases/test-cli-crawl-wiring.md) — Cli crawl wiring. _(BANKED)_
* [test_cli_haggle_wiring.py](/testing/cases/test-cli-haggle-wiring.md) — Cli haggle wiring. _(BANKED)_
* [test_cli_log.py](/testing/cases/test-cli-log.md) — Cli log.
* [test_cli_menumap.py](/testing/cases/test-cli-menumap.md) — `tw menumap` wiring + fixture printout (WO-P2-OPS-VERB-G1).
* [test_cli_ops_verb_a.py](/testing/cases/test-cli-ops-verb-a.md) — Cli ops verb a.
* [test_cli_ops_verb_b.py](/testing/cases/test-cli-ops-verb-b.md) — Cli ops verb b.
* [test_cli_ops_verb_c.py](/testing/cases/test-cli-ops-verb-c.md) — Cli ops verb c.
* [test_cli_ops_verb_e2.py](/testing/cases/test-cli-ops-verb-e2.md) — Cli ops verb e2.
* [test_cli_players.py](/testing/cases/test-cli-players.md) — `tw players` CLI verb tests -- no daemon involved, direct state/player_bank.json access (TW-31 client-side wiring, v1). _(BANKED)_
* [test_cli_run_dir.py](/testing/cases/test-cli-run-dir.md) — WO-P2-021 — CLI / daemon run-dir wiring against the reborn session API.
* [test_cockpit_arm_pty.py](/testing/cases/test-cockpit-arm-pty.md) — WO-P5-062 Accept #4 -- the ARM indicator on a real terminal.
* [test_cockpit_arm_wiring.py](/testing/cases/test-cockpit-arm-wiring.md) — Cockpit arm wiring.
* [test_cockpit_attach.py](/testing/cases/test-cockpit-attach.md) — Cockpit attach.
* [test_cockpit_decisions.py](/testing/cases/test-cockpit-decisions.md) — Pure DECISIONS-panel composer tests (PWO-036, Layer-A).
* [test_cockpit_decisions_pty.py](/testing/cases/test-cockpit-decisions-pty.md) — WO-P3-036 wire — DECISIONS panel stacked below HUD, Layer-B.
* [test_cockpit_draw_runs.py](/testing/cases/test-cockpit-draw-runs.md) — Cockpit draw runs.
* [test_cockpit_focus.py](/testing/cases/test-cockpit-focus.md) — Pure FOCUS-panel composer tests (PWO-035, Layer-A).
* [test_cockpit_focus_pty.py](/testing/cases/test-cockpit-focus-pty.md) — WO-P3-035 wire — FOCUS panel retitle + live compose, Layer-B.
* [test_cockpit_fold.py](/testing/cases/test-cockpit-fold.md) — Pure responsive-fold composer tests (WO-P3-039, Layer-A).
* [test_cockpit_fold_pty.py](/testing/cases/test-cockpit-fold-pty.md) — WO-P3-039 wire -- responsive fold, Layer-B.
* [test_cockpit_frame_pty.py](/testing/cases/test-cockpit-frame-pty.md) — WO-P3-030-033 — Trainer-cockpit frame chrome (PWO-031/033), Layer-B.
* [test_cockpit_goals.py](/testing/cases/test-cockpit-goals.md) — Pure GOALS-panel composer tests (PWO-034, Layer-A).
* [test_cockpit_goals_pty.py](/testing/cases/test-cockpit-goals-pty.md) — WO-P3-034 wire — GOALS panel + 1 Hz status_provider refresh, Layer-B.
* [test_cockpit_hud.py](/testing/cases/test-cockpit-hud.md) — Pure HUD-panel composer tests (PWO-037, Layer-A).
* [test_cockpit_hud_pty.py](/testing/cases/test-cockpit-hud-pty.md) — WO-P3-037 wire -- HUD freshness markers, Layer-B.
* [test_cockpit_layout.py](/testing/cases/test-cockpit-layout.md) — Trainer-cockpit frame geometry tests (PWO-031/033, Layer-A).
* [test_cockpit_liveness.py](/testing/cases/test-cockpit-liveness.md) — Pure liveness-cluster composer tests (WO-P3-038, Layer-A).
* [test_cockpit_liveness_pty.py](/testing/cases/test-cockpit-liveness-pty.md) — WO-P3-038 wire -- control-strip liveness cluster, Layer-B.
* [test_cockpit_logsband.py](/testing/cases/test-cockpit-logsband.md) — Pure LOGS-band composer tests (WO-P3-041, Layer-A).
* [test_cockpit_logsband_pty.py](/testing/cases/test-cockpit-logsband-pty.md) — WO-P3-041 wire -- LOGS band advancing transcript tail + newest-row flash, Layer-B.
* [test_cockpit_mode_badge.py](/testing/cases/test-cockpit-mode-badge.md) — WO-P5-060 lane B -- App/Human control-strip mode-badge wiring.
* [test_cockpit_spectate.py](/testing/cases/test-cockpit-spectate.md) — Cockpit spectate.
* [test_cockpit_stopbanner.py](/testing/cases/test-cockpit-stopbanner.md) — WO-P5-064 Layer-A -- the STOP banner composed from TYPED reason codes.
* [test_cockpit_stopbanner_wiring.py](/testing/cases/test-cockpit-stopbanner-wiring.md) — Cockpit stopbanner wiring.
* [test_cockpit_strip.py](/testing/cases/test-cockpit-strip.md) — Pure profile/character-strip composer tests (PWO-032, Layer-A).
* [test_cockpit_tones.py](/testing/cases/test-cockpit-tones.md) — Pure semantic-tone module tests (WO-P3-040, Layer-A).
* [test_cockpit_tones_pty.py](/testing/cases/test-cockpit-tones-pty.md) — WO-P3-040 wire — semantic chrome tones, Layer-B.
* [test_cockpit_viewport.py](/testing/cases/test-cockpit-viewport.md) — PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake window, no pty/curses init needed).
* [test_cockpit_viewport_color.py](/testing/cases/test-cockpit-viewport-color.md) — Cockpit viewport color.
* [test_cockpit_viewport_paint.py](/testing/cases/test-cockpit-viewport-paint.md) — Layer-A tests for the GAME viewport paint composer (WO-P4-052).
* [test_cockpit_viewport_paint_color.py](/testing/cases/test-cockpit-viewport-paint-color.md) — Cockpit viewport paint color.
* [test_cockpit_viewport_paint_pty.py](/testing/cases/test-cockpit-viewport-paint-pty.md) — WO-P4-052, lane B -- GAME viewport LIVE PAINT, real-curses pty proof.
* [test_cockpit_viewport_pty.py](/testing/cases/test-cockpit-viewport-pty.md) — WO-P4-051, lane B -- GAME viewport shell, real-curses pty proof.
* [test_connection.py](/testing/cases/test-connection.md) — TelnetConnection unit tests — no network.
* [test_control_lock.py](/testing/cases/test-control-lock.md) — ControlLock (tw2002_aiclient.session.control_lock) — pure unit tests.
* [test_control_panel.py](/testing/cases/test-control-panel.md) — Control panel. _(BANKED)_
* [test_crawl_start_protocol.py](/testing/cases/test-crawl-start-protocol.md) — Crawl start protocol. _(BANKED)_
* [test_credentials.py](/testing/cases/test-credentials.md) — Secure credential store tests (DESIGN-v2 B2) — no network, tmp_path only, never touches the real config/ directory. _(BANKED)_
* [test_ensure_from_play.py](/testing/cases/test-ensure-from-play.md) — Ensure from play.
* [test_ensure_no_auto_arm.py](/testing/cases/test-ensure-no-auto-arm.md) — WO-P2-022 — ensure never surprise-arms App autopilot.
* [test_ensure_protocol.py](/testing/cases/test-ensure-protocol.md) — Ensure protocol.
* [test_env.py](/testing/cases/test-env.md) — .env loader + host/port + run-dir resolution (no network).
* [test_explore.py](/testing/cases/test-explore.md) — TW-14 Map-fill / frontier explore planner tests. _(BANKED)_
* [test_fighter_toll_policy.py](/testing/cases/test-fighter-toll-policy.md) — WO-FIGHTER-FLOOR-TOLL — fighter reserve + Option? _(BANKED)_
* [test_formations.py](/testing/cases/test-formations.md) — TW-16 formation detector tests. _(BANKED)_
* [test_frame_recorder.py](/testing/cases/test-frame-recorder.md) — WO-FRAMES-0 — frame recorder + build_response hook + CLI read path. _(BANKED)_
* [test_game_data.py](/testing/cases/test-game-data.md) — TW-24 game_data schema/loader tests. _(BANKED)_
* [test_game_data_persist.py](/testing/cases/test-game-data-persist.md) — Game data persist. _(BANKED)_
* [test_game_knowledge.py](/testing/cases/test-game-knowledge.md) — Game Knowledge Store tests (TW-25) -- no network, tmp_path only, never touches the real config/ or state/ directories. _(BANKED)_
* [test_game_knowledge_learned_rules.py](/testing/cases/test-game-knowledge-learned-rules.md) — Learned-rule store tests — offline, tmp_path only. _(BANKED)_
* [test_glyph_table_dedupe.py](/testing/cases/test-glyph-table-dedupe.md) — Glyph table dedupe.
* [test_guardian.py](/testing/cases/test-guardian.md) — SessionGuardian tests (WO-P2-027 reconnect+replay; WO-P2-028 keepalive).
* [test_haggle.py](/testing/cases/test-haggle.md) — Haggle. _(BANKED)_
* [test_hud_seed.py](/testing/cases/test-hud-seed.md) — WO-HUD-CREDITS-TURNS-JOIN — cold-join I-probe + sticky turns. _(BANKED)_
* [test_iac.py](/testing/cases/test-iac.md) — IAC stripping + negotiation tests — no network involved.
* [test_integration_introspect_persist.py](/testing/cases/test-integration-introspect-persist.md) — TW-26/27 introspector-to-persist chain integration test. _(BANKED)_
* [test_interactive_app.py](/testing/cases/test-interactive-app.md) — Interactive app. _(BANKED)_
* [test_intervention_labels.py](/testing/cases/test-intervention-labels.md) — Shared intervention label map — single source for play + spectate. _(BANKED)_
* [test_introspector.py](/testing/cases/test-introspector.md) — TW-27 game-data introspector tests. _(BANKED)_
* [test_ledger.py](/testing/cases/test-ledger.md) — Ledger. _(BANKED)_
* [test_logging_util.py](/testing/cases/test-logging-util.md) — Transcript logger tests — no network involved.
* [test_login.py](/testing/cases/test-login.md) — Login.
* [test_login_redaction.py](/testing/cases/test-login-redaction.md) — Login redaction. _(BANKED)_
* [test_login_resume.py](/testing/cases/test-login-resume.md) — Login resume.
* [test_menu_crawler.py](/testing/cases/test-menu-crawler.md) — Menu Crawler tests (TW-26) -- no network, mock/fixture screens only. _(BANKED)_
* [test_menu_map_view.py](/testing/cases/test-menu-map-view.md) — Menu-map inspector — pure tests on synthetic maps.
* [test_menu_nav.py](/testing/cases/test-menu-nav.md) — Menu localize + plan_nav — pure tests on synthetic maps.
* [test_menu_sig.py](/testing/cases/test-menu-sig.md) — menu.sig.menu_signature — the shared, pure signature primitive.
* [test_miner.py](/testing/cases/test-miner.md) — Miner. _(BANKED)_
* [test_mode_badge_vocabulary.py](/testing/cases/test-mode-badge-vocabulary.md) — Mode badge vocabulary.
* [test_name_bank.py](/testing/cases/test-name-bank.md) — Name bank tests (WO-MS-4 rider) -- no network, tmp_path only. _(BANKED)_
* [test_play_chrome_nav.py](/testing/cases/test-play-chrome-nav.md) — WO-P3-030 — Play-chrome navigation (Esc → launcher, daemon survives).
* [test_play_esc_daemon_survival.py](/testing/cases/test-play-esc-daemon-survival.md) — Play esc daemon survival.
* [test_player_bank.py](/testing/cases/test-player-bank.md) — Player bank stub tests (WO-P1-015) — metadata-only list_players.
* [test_probe.py](/testing/cases/test-probe.md) — WO-MS-3 probe tests — classification, polite envelope, L0/L1 invariants. _(BANKED)_
* [test_profile_resolver.py](/testing/cases/test-profile-resolver.md) — Profile resolver.
* [test_protocol_build_response_color.py](/testing/cases/test-protocol-build-response-color.md) — Protocol build response color.
* [test_protocol_haggle.py](/testing/cases/test-protocol-haggle.md) — Protocol haggle. _(BANKED)_
* [test_protocol_trainer_panel.py](/testing/cases/test-protocol-trainer-panel.md) — Protocol trainer panel. _(BANKED)_
* [test_pty_helpers.py](/testing/cases/test-pty-helpers.md) — Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2).
* [test_pty_helpers_smoke.py](/testing/cases/test-pty-helpers-smoke.md) — WO-P3-HARNESS-REHAB D1 lane-3 — smallest Accept proof for pty helpers.
* [test_replay_ledger_integration.py](/testing/cases/test-replay-ledger-integration.md) — Replay ledger integration. _(BANKED)_
* [test_safe_addstr_choke.py](/testing/cases/test-safe-addstr-choke.md) — Safe addstr choke.
* [test_screens_shared_pairs.py](/testing/cases/test-screens-shared-pairs.md) — Screens shared pairs.
* [test_servers.py](/testing/cases/test-servers.md) — WO-MS-1 server catalog tests. _(BANKED)_
* [test_session.py](/testing/cases/test-session.md) — Session unit tests — no network.
* [test_settle.py](/testing/cases/test-settle.md) — Settle-detection timing tests with a fake clock — no real sleeping.
* [test_ship_upgrade_decision.py](/testing/cases/test-ship-upgrade-decision.md) — TW-30 ship-upgrade decision engine — unit coverage for all five §24 learnings. _(BANKED)_
* [test_skills.py](/testing/cases/test-skills.md) — Skill record/replay + playback tests (DESIGN-v2 §3 v2.1 item 11b/11d, C3) -- no network. _(BANKED)_
* [test_spectate_app.py](/testing/cases/test-spectate-app.md) — **REMOVED** (ops `tw spectate` RETIRED; tip = `test_cockpit_spectate.py`). Historical case inventory only.
* [test_spectate_layout.py](/testing/cases/test-spectate-layout.md) — **REMOVED** (archive `spectate_layout.py` deleted). Historical case inventory only.
* [test_spectate_no_send.py](/testing/cases/test-spectate-no-send.md) — Spectate no send.
* [test_state_parser.py](/testing/cases/test-state-parser.md) — Best-effort state-extraction tests — no network involved. _(BANKED)_
* [test_terminal.py](/testing/cases/test-terminal.md) — pyte render + crop correctness tests — no network involved.
* [test_trade_adapter.py](/testing/cases/test-trade-adapter.md) — Trade adapter. _(BANKED)_
* [test_trade_driver.py](/testing/cases/test-trade-driver.md) — tests/test_trade_driver.py -- WO-FA4 trade_driver.py: the money-path chain-execution driver. _(BANKED)_
* [test_transcript_tail.py](/testing/cases/test-transcript-tail.md) — Session-side redacted transcript ring buffer (WO-P3-041 LOGS band).
* [test_tw04_toctou.py](/testing/cases/test-tw04-toctou.md) — TW-04 TOCTOU / refuse-not-queue probes (WO-P2-025).
* [test_unicode_ok_delegation.py](/testing/cases/test-unicode-ok-delegation.md) — Unicode ok delegation.
* [test_watch.py](/testing/cases/test-watch.md) — Watch.
* [test_watchfeed.py](/testing/cases/test-watchfeed.md) — Watchfeed.
* [test_watchfeed_wire.py](/testing/cases/test-watchfeed-wire.md) — WO-P4-050 (wire lane) — WatchFeed lifecycle wired into the play shell.
* [test_world_identity.py](/testing/cases/test-world-identity.md) — World identity. _(BANKED)_
* [test_world_model.py](/testing/cases/test-world-model.md) — World model tests (TW-06) -- no network, tmp_path only, never touches the real state/ directory. _(BANKED)_
* [test_world_model_integration.py](/testing/cases/test-world-model-integration.md) — World model integration. _(BANKED)_
