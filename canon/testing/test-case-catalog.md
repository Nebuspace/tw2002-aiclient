---
type: Reference
title: Test Case Catalog
description: Inventory of every pytest case in tw2002-aiclient with a one-sentence blurb of what each asserts.
resource: repo://tw2002-aiclient/tests
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T05:30:00Z
---

# Test Case Catalog

Module inventory and per-test blurbs below may lag tip (many modules were added after the
2026-07-25 full pass). **Headline counts re-verified 2026-08-09 against tip** via actual
collection (not AST estimate):

```text
.venv/bin/python -m pytest -n0 --collect-only
→ 7437 tests collected   # footer is authoritative
.venv/bin/python -m pytest -n0 --collect-only -q
→ 308 lines of form tests/test_*.py: <n>  (sum == 7437)
```

`tests/test_*.py` on disk: **310** files. Default collect excludes the 2 BANKED ignores below.

Each module *should* link to a per-module OKF case file with per-test blurbs (regeneration of
every case file is a separate catalog-refresh WO — this pass only corrects the stale headline
counts).

- **Active (default run):** 308 modules · **7437** tests
- **BANKED (ignored via `pytest.ini`):** 2 modules — `tests/test_analyze.py`,
  `tests/test_crawl_start_protocol.py` (still `import twclient`; collection ERRORs if un-ignored;
  not included in the 7437)

> **Blurb rule:** first complete sentence of the function docstring when it is well-formed (ends with `.!?`, no truncated backticks); otherwise readable English derived from the `test_*` name. No runtime behavior is invented beyond name/docstring.

> **BANKED** modules are excluded from the default pytest run via `pytest.ini --ignore`. They are catalogued for completeness. See `workorders/WO-TEST-SUITE-REHAB.md` for the rehabilitation plan.

## Cockpit & UI

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_aiclient_play_panels.py`](/testing/cases/test-aiclient-play-panels.md) | 8 | BANKED | Aiclient play panels. |
| [`test_cockpit_arm_pty.py`](/testing/cases/test-cockpit-arm-pty.md) | 5 | active | WO-P5-062 Accept #4 -- the ARM indicator on a real terminal. |
| [`test_cockpit_arm_wiring.py`](/testing/cases/test-cockpit-arm-wiring.md) | 26 | active | Cockpit arm wiring. |
| [`test_cockpit_attach.py`](/testing/cases/test-cockpit-attach.md) | 26 | active | WO-P4-056 lane A -- Ctrl-A attaches the cockpit to the daemon's Human control lock (canon `mode-line-and-teach-controls.md:40-47`). |
| [`test_cockpit_decisions.py`](/testing/cases/test-cockpit-decisions.md) | 36 | active | Pure DECISIONS-panel composer tests (PWO-036, Layer-A). |
| [`test_cockpit_decisions_pty.py`](/testing/cases/test-cockpit-decisions-pty.md) | 7 | active | WO-P3-036 wire — DECISIONS panel stacked below HUD, Layer-B. |
| [`test_cockpit_draw_runs.py`](/testing/cases/test-cockpit-draw-runs.md) | 26 | active | Cockpit draw runs. |
| [`test_cockpit_focus.py`](/testing/cases/test-cockpit-focus.md) | 32 | active | Pure FOCUS-panel composer tests (PWO-035, Layer-A). |
| [`test_cockpit_focus_pty.py`](/testing/cases/test-cockpit-focus-pty.md) | 7 | active | WO-P3-035 wire — FOCUS panel retitle + live compose, Layer-B. |
| [`test_cockpit_fold.py`](/testing/cases/test-cockpit-fold.md) | 18 | active | Pure responsive-fold composer tests (WO-P3-039, Layer-A). |
| [`test_cockpit_fold_pty.py`](/testing/cases/test-cockpit-fold-pty.md) | 8 | active | WO-P3-039 wire -- responsive fold, Layer-B. |
| [`test_cockpit_frame_pty.py`](/testing/cases/test-cockpit-frame-pty.md) | 15 | active | WO-P3-030-033 — Trainer-cockpit frame chrome (PWO-031/033), Layer-B. |
| [`test_cockpit_goals.py`](/testing/cases/test-cockpit-goals.md) | 30 | active | Pure GOALS-panel composer tests (PWO-034, Layer-A). |
| [`test_cockpit_goals_pty.py`](/testing/cases/test-cockpit-goals-pty.md) | 6 | active | WO-P3-034 wire — GOALS panel + 1 Hz status_provider refresh, Layer-B. |
| [`test_cockpit_hud.py`](/testing/cases/test-cockpit-hud.md) | 52 | active | Pure HUD-panel composer tests (PWO-037, Layer-A). |
| [`test_cockpit_hud_pty.py`](/testing/cases/test-cockpit-hud-pty.md) | 12 | active | WO-P3-037 wire -- HUD freshness markers, Layer-B. |
| [`test_cockpit_layout.py`](/testing/cases/test-cockpit-layout.md) | 39 | active | Trainer-cockpit frame geometry tests (PWO-031/033, Layer-A). |
| [`test_cockpit_liveness.py`](/testing/cases/test-cockpit-liveness.md) | 54 | active | Pure liveness-cluster composer tests (WO-P3-038, Layer-A). |
| [`test_cockpit_liveness_pty.py`](/testing/cases/test-cockpit-liveness-pty.md) | 9 | active | WO-P3-038 wire -- control-strip liveness cluster, Layer-B. |
| [`test_cockpit_logsband.py`](/testing/cases/test-cockpit-logsband.md) | 47 | active | Pure LOGS-band composer tests (WO-P3-041, Layer-A). |
| [`test_cockpit_logsband_pty.py`](/testing/cases/test-cockpit-logsband-pty.md) | 14 | active | WO-P3-041 wire -- LOGS band advancing transcript tail + newest-row flash, Layer-B. |
| [`test_cockpit_mode_badge.py`](/testing/cases/test-cockpit-mode-badge.md) | 15 | active | WO-P5-060 lane B -- App/Human control-strip mode-badge wiring. |
| [`test_cockpit_spectate.py`](/testing/cases/test-cockpit-spectate.md) | 69 | active | Cockpit spectate. |
| [`test_cockpit_stopbanner.py`](/testing/cases/test-cockpit-stopbanner.md) | 28 | active | WO-P5-064 Layer-A -- the STOP banner composed from TYPED reason codes. |
| [`test_cockpit_stopbanner_wiring.py`](/testing/cases/test-cockpit-stopbanner-wiring.md) | 17 | active | Cockpit stopbanner wiring. |
| [`test_cockpit_strip.py`](/testing/cases/test-cockpit-strip.md) | 30 | active | Pure profile/character-strip composer tests (PWO-032, Layer-A). |
| [`test_cockpit_tones.py`](/testing/cases/test-cockpit-tones.md) | 34 | active | Pure semantic-tone module tests (WO-P3-040, Layer-A). |
| [`test_cockpit_tones_pty.py`](/testing/cases/test-cockpit-tones-pty.md) | 19 | active | WO-P3-040 wire — semantic chrome tones, Layer-B. |
| [`test_cockpit_viewport.py`](/testing/cases/test-cockpit-viewport.md) | 2 | active | PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake window, no pty/curses init needed). |
| [`test_cockpit_viewport_color.py`](/testing/cases/test-cockpit-viewport-color.md) | 23 | active | Cockpit viewport color. |
| [`test_cockpit_viewport_paint.py`](/testing/cases/test-cockpit-viewport-paint.md) | 17 | active | Layer-A tests for the GAME viewport paint composer (WO-P4-052). |
| [`test_cockpit_viewport_paint_color.py`](/testing/cases/test-cockpit-viewport-paint-color.md) | 5 | active | Cockpit viewport paint color. |
| [`test_cockpit_viewport_paint_pty.py`](/testing/cases/test-cockpit-viewport-paint-pty.md) | 8 | active | WO-P4-052, lane B -- GAME viewport LIVE PAINT, real-curses pty proof. |
| [`test_cockpit_viewport_pty.py`](/testing/cases/test-cockpit-viewport-pty.md) | 10 | active | WO-P4-051, lane B -- GAME viewport shell, real-curses pty proof. |
| [`test_screens_shared_pairs.py`](/testing/cases/test-screens-shared-pairs.md) | 15 | active | Screens shared pairs. |

## CLI Verbs & Entry Points

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_cli_attach_interactive_send_failure.py`](/testing/cases/test-cli-attach-interactive-send-failure.md) | 8 | active | Cli attach interactive send failure. |
| [`test_cli_attach_keys_exit_code.py`](/testing/cases/test-cli-attach-keys-exit-code.md) | 3 | active | Cli attach keys exit code. |
| [`test_cli_crawl_wiring.py`](/testing/cases/test-cli-crawl-wiring.md) | 3 | BANKED | `tw crawl` CLI verb wiring -- argparse only (dispatch itself needs a live daemon and is exercised at the protocol layer instead, see tests/test_crawl_start_protocol.py). |
| [`test_cli_haggle_wiring.py`](/testing/cases/test-cli-haggle-wiring.md) | 2 | BANKED | `tw haggle` CLI verb wiring -- argparse only (dispatch itself needs a live daemon and is exercised at the protocol layer instead, see tests/test_protocol_haggle.py). |
| [`test_cli_log.py`](/testing/cases/test-cli-log.md) | 3 | active | Cli log. |
| [`test_cli_menumap.py`](/testing/cases/test-cli-menumap.md) | 7 | active | `tw menumap` wiring + fixture printout (WO-P2-OPS-VERB-G1). |
| [`test_cli_ops_verb_a.py`](/testing/cases/test-cli-ops-verb-a.md) | 7 | active | Cli ops verb a. |
| [`test_cli_ops_verb_b.py`](/testing/cases/test-cli-ops-verb-b.md) | 7 | active | Cli ops verb b. |
| [`test_cli_ops_verb_c.py`](/testing/cases/test-cli-ops-verb-c.md) | 4 | active | Cli ops verb c. |
| [`test_cli_ops_verb_e2.py`](/testing/cases/test-cli-ops-verb-e2.md) | 3 | active | Cli ops verb e2. |
| [`test_cli_players.py`](/testing/cases/test-cli-players.md) | 20 | BANKED | `tw players` CLI verb tests -- no daemon involved, direct state/player_bank.json access (TW-31 client-side wiring, v1). |
| [`test_cli_run_dir.py`](/testing/cases/test-cli-run-dir.md) | 12 | active | WO-P2-021 — CLI / daemon run-dir wiring against the reborn session API. |
| [`test_unicode_ok_delegation.py`](/testing/cases/test-unicode-ok-delegation.md) | 3 | active | Unicode ok delegation. |

## Menu Map & Navigation

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_crawl_start_protocol.py`](/testing/cases/test-crawl-start-protocol.md) | 6 | BANKED | protocol.py's `crawl_start` verb dispatch -- no network, same bare dispatch-harness convention as tests/test_protocol_haggle.py/ test_actor_attribution.py. |
| [`test_menu_crawler.py`](/testing/cases/test-menu-crawler.md) | 63 | BANKED | Menu Crawler tests (TW-26) -- no network, mock/fixture screens only. |
| [`test_menu_map_view.py`](/testing/cases/test-menu-map-view.md) | 9 | active | Menu-map inspector — pure tests on synthetic maps. |
| [`test_menu_nav.py`](/testing/cases/test-menu-nav.md) | 9 | active | Menu localize + plan_nav — pure tests on synthetic maps. |
| [`test_menu_sig.py`](/testing/cases/test-menu-sig.md) | 5 | active | menu.sig.menu_signature — the shared, pure signature primitive. |

## Attach & Keystroke Honesty

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_attach_client_timeouts.py`](/testing/cases/test-attach-client-timeouts.md) | 5 | active | AttachInputConn socket-op timeouts (HARDEN-ATTACH). |
| [`test_attach_protocol.py`](/testing/cases/test-attach-protocol.md) | 7 | active | Attach control-lock handoff over a real unix socket + FakeAttachSession. |
| [`test_attach_redaction.py`](/testing/cases/test-attach-redaction.md) | 8 | active | Attach keystroke secret redaction (WO-P2-OPS-VERB-F1b). |

## Spectate & Watch

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_spectate_app.py`](/testing/cases/test-spectate-app.md) | 78 | **REMOVED** | Ops `tw spectate` / `spectate_app.py` **RETIRED** — module deleted; tip observation is `test_cockpit_spectate.py` + `tw watch`. Case file kept as historical inventory only. |
| [`test_spectate_layout.py`](/testing/cases/test-spectate-layout.md) | 170 | **REMOVED** | Archive `spectate_layout.py` deleted with ops spectate; tip layout tests live under `cockpit/` modules. Case file historical only. |
| [`test_spectate_no_send.py`](/testing/cases/test-spectate-no-send.md) | 13 | active | Spectate no send. |
| [`test_watch.py`](/testing/cases/test-watch.md) | 14 | active | Watch. |
| [`test_watchfeed.py`](/testing/cases/test-watchfeed.md) | 10 | active | Watchfeed. |
| [`test_watchfeed_wire.py`](/testing/cases/test-watchfeed-wire.md) | 5 | active | WO-P4-050 (wire lane) — WatchFeed lifecycle wired into the play shell. |

## World & Navigation

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_play_chrome_nav.py`](/testing/cases/test-play-chrome-nav.md) | 4 | active | WO-P3-030 — Play-chrome navigation (Esc → launcher, daemon survives). |
| [`test_world_identity.py`](/testing/cases/test-world-identity.md) | 13 | BANKED | World identity. |
| [`test_world_model.py`](/testing/cases/test-world-model.md) | 53 | BANKED | World model tests (TW-06) -- no network, tmp_path only, never touches the real state/ directory. |
| [`test_world_model_integration.py`](/testing/cases/test-world-model-integration.md) | 21 | BANKED | World model integration. |

## Game / Trade

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_game_data.py`](/testing/cases/test-game-data.md) | 5 | BANKED | TW-24 game_data schema/loader tests. |
| [`test_game_data_persist.py`](/testing/cases/test-game-data-persist.md) | 25 | BANKED | TW-26/27 write lane -- persist/query path tests for `game_data.py`'s bridge over `game_knowledge.py`'s per-world "ships" game-data table. |
| [`test_game_knowledge.py`](/testing/cases/test-game-knowledge.md) | 43 | BANKED | Game Knowledge Store tests (TW-25) -- no network, tmp_path only, never touches the real config/ or state/ directories. |
| [`test_game_knowledge_learned_rules.py`](/testing/cases/test-game-knowledge-learned-rules.md) | 6 | BANKED | Learned-rule store tests — offline, tmp_path only. |
| [`test_haggle.py`](/testing/cases/test-haggle.md) | 16 | BANKED | Haggle. |
| [`test_protocol_haggle.py`](/testing/cases/test-protocol-haggle.md) | 6 | BANKED | Protocol haggle. |
| [`test_trade_adapter.py`](/testing/cases/test-trade-adapter.md) | 28 | BANKED | WO-FA3 trade_adapter tests -- synthetic world-model fixtures only, no live daemon, no network (same tmp_path/state_dir convention as test_world_model.py). |
| [`test_trade_driver.py`](/testing/cases/test-trade-driver.md) | 16 | BANKED | tests/test_trade_driver.py -- WO-FA4 trade_driver.py: the money-path chain-execution driver. |

## Session / Protocol / Transcript

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_connection.py`](/testing/cases/test-connection.md) | 7 | active | TelnetConnection unit tests — no network. |
| [`test_ensure_protocol.py`](/testing/cases/test-ensure-protocol.md) | 6 | active | Ensure protocol. |
| [`test_play_esc_daemon_survival.py`](/testing/cases/test-play-esc-daemon-survival.md) | 3 | active | Play esc daemon survival. |
| [`test_protocol_build_response_color.py`](/testing/cases/test-protocol-build-response-color.md) | 11 | active | Protocol build response color. |
| [`test_protocol_trainer_panel.py`](/testing/cases/test-protocol-trainer-panel.md) | 31 | BANKED | Protocol trainer panel. |
| [`test_session.py`](/testing/cases/test-session.md) | 16 | active | Session unit tests — no network. |
| [`test_transcript_tail.py`](/testing/cases/test-transcript-tail.md) | 14 | active | Session-side redacted transcript ring buffer (WO-P3-041 LOGS band). |

## Engine & Utilities

| Module | Tests | Status | Blurb |
|--------|-------|--------|-------|
| [`test_actor_attribution.py`](/testing/cases/test-actor-attribution.md) | 9 | active | Actor attribution at the send choke point (WO-P2-025). |
| [`test_aiclient_adapters.py`](/testing/cases/test-aiclient-adapters.md) | 24 | BANKED | Unit tests for tw2002_aiclient ensure/autopilot adapters (mocked daemon). |
| [`test_analyze.py`](/testing/cases/test-analyze.md) | 5 | BANKED | TW-12 session-retro analyzer tests — no network, synthetic ledger only. |
| [`test_chains.py`](/testing/cases/test-chains.md) | 6 | BANKED | TW-21 longest-profit-chain algorithm tests (synthetic graphs). |
| [`test_classify.py`](/testing/cases/test-classify.md) | 53 | active | Screen classifier tests: synthetic anchor coverage + a real captured TWGS screen fixture (see tests/fixtures/, captured live (historical DoD; see session-engine / screen-understanding)). |
| [`test_clean_preempt.py`](/testing/cases/test-clean-preempt.md) | 11 | BANKED | Clean preempt. |
| [`test_control_lock.py`](/testing/cases/test-control-lock.md) | 37 | active | ControlLock (tw2002_aiclient.session.control_lock) — pure unit tests. |
| [`test_control_panel.py`](/testing/cases/test-control-panel.md) | 6 | BANKED | Control panel. |
| [`test_credentials.py`](/testing/cases/test-credentials.md) | 28 | BANKED | Secure credential store tests (DESIGN-v2 B2) — no network, tmp_path only, never touches the real config/ directory. |
| [`test_ensure_from_play.py`](/testing/cases/test-ensure-from-play.md) | 2 | active | Ensure from play. |
| [`test_ensure_no_auto_arm.py`](/testing/cases/test-ensure-no-auto-arm.md) | 6 | active | WO-P2-022 — ensure never surprise-arms App autopilot. |
| [`test_env.py`](/testing/cases/test-env.md) | 21 | active | .env loader + host/port + run-dir resolution (no network). |
| [`test_explore.py`](/testing/cases/test-explore.md) | 18 | BANKED | TW-14 Map-fill / frontier explore planner tests. |
| [`test_fighter_toll_policy.py`](/testing/cases/test-fighter-toll-policy.md) | 16 | BANKED | WO-FIGHTER-FLOOR-TOLL — fighter reserve + Option? |
| [`test_formations.py`](/testing/cases/test-formations.md) | 6 | BANKED | TW-16 formation detector tests. |
| [`test_frame_recorder.py`](/testing/cases/test-frame-recorder.md) | 5 | BANKED | WO-FRAMES-0 — frame recorder + build_response hook + CLI read path. |
| [`test_glyph_table_dedupe.py`](/testing/cases/test-glyph-table-dedupe.md) | 8 | active | Glyph table dedupe. |
| [`test_guardian.py`](/testing/cases/test-guardian.md) | 16 | active | SessionGuardian tests (WO-P2-027 reconnect+replay; WO-P2-028 keepalive). |
| [`test_hud_seed.py`](/testing/cases/test-hud-seed.md) | 3 | BANKED | WO-HUD-CREDITS-TURNS-JOIN — cold-join I-probe + sticky turns. |
| [`test_iac.py`](/testing/cases/test-iac.md) | 12 | active | IAC stripping + negotiation tests — no network involved. |
| [`test_integration_introspect_persist.py`](/testing/cases/test-integration-introspect-persist.md) | 3 | BANKED | TW-26/27 introspector-to-persist chain integration test. |
| [`test_interactive_app.py`](/testing/cases/test-interactive-app.md) | 5 | BANKED | Interactive app. |
| [`test_intervention_labels.py`](/testing/cases/test-intervention-labels.md) | 3 | BANKED | Shared intervention label map — single source for play + spectate. |
| [`test_introspector.py`](/testing/cases/test-introspector.md) | 19 | BANKED | TW-27 game-data introspector tests. |
| [`test_ledger.py`](/testing/cases/test-ledger.md) | 31 | BANKED | Trace-Ledger tests (DESIGN-v2 §3 v2.1 item 11a, C1) -- no network, tmp_path only, never touches the real state/ directory. |
| [`test_logging_util.py`](/testing/cases/test-logging-util.md) | 5 | active | Transcript logger tests — no network involved. |
| [`test_login.py`](/testing/cases/test-login.md) | 5 | active | Login. |
| [`test_login_redaction.py`](/testing/cases/test-login-redaction.md) | 13 | BANKED | Cipher security gate (2026-07-20): sentinel-password redaction proof across the TW-02 `send_and_confirm` login/password swap (a2e99f6). |
| [`test_login_resume.py`](/testing/cases/test-login-resume.md) | 4 | active | Login resume. |
| [`test_miner.py`](/testing/cases/test-miner.md) | 12 | BANKED | Miner. |
| [`test_mode_badge_vocabulary.py`](/testing/cases/test-mode-badge-vocabulary.md) | 9 | active | Mode badge vocabulary. |
| [`test_name_bank.py`](/testing/cases/test-name-bank.md) | 11 | BANKED | Name bank tests (WO-MS-4 rider) -- no network, tmp_path only. |
| [`test_player_bank.py`](/testing/cases/test-player-bank.md) | 8 | active | Player bank stub tests (WO-P1-015) — metadata-only list_players. |
| [`test_probe.py`](/testing/cases/test-probe.md) | 12 | BANKED | WO-MS-3 probe tests — classification, polite envelope, L0/L1 invariants. |
| [`test_profile_resolver.py`](/testing/cases/test-profile-resolver.md) | 10 | active | Profile resolver. |
| [`test_pty_helpers.py`](/testing/cases/test-pty-helpers.md) | 7 | active | Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2). |
| [`test_pty_helpers_smoke.py`](/testing/cases/test-pty-helpers-smoke.md) | 6 | active | WO-P3-HARNESS-REHAB D1 lane-3 — smallest Accept proof for pty helpers. |
| [`test_replay_ledger_integration.py`](/testing/cases/test-replay-ledger-integration.md) | 4 | BANKED | Replay ledger integration. |
| [`test_safe_addstr_choke.py`](/testing/cases/test-safe-addstr-choke.md) | 8 | active | Safe addstr choke. |
| [`test_servers.py`](/testing/cases/test-servers.md) | 7 | BANKED | WO-MS-1 server catalog tests. |
| [`test_settle.py`](/testing/cases/test-settle.md) | 25 | active | Settle-detection timing tests with a fake clock — no real sleeping. |
| [`test_ship_upgrade_decision.py`](/testing/cases/test-ship-upgrade-decision.md) | 10 | BANKED | TW-30 ship-upgrade decision engine — unit coverage for all five §24 learnings. |
| [`test_skills.py`](/testing/cases/test-skills.md) | 50 | BANKED | Skill record/replay + playback tests (DESIGN-v2 §3 v2.1 item 11b/11d, C3) -- no network. |
| [`test_state_parser.py`](/testing/cases/test-state-parser.md) | 62 | BANKED | Best-effort state-extraction tests — no network involved. |
| [`test_terminal.py`](/testing/cases/test-terminal.md) | 13 | active | pyte render + crop correctness tests — no network involved. |
| [`test_tw04_toctou.py`](/testing/cases/test-tw04-toctou.md) | 7 | active | TW-04 TOCTOU / refuse-not-queue probes (WO-P2-025). |

