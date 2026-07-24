# WO-TEST-SUITE-REHAB — Stale `twclient` test inventory + rehab plan

> Status: PLANNED (inventory SHIP `7e75677` · **DELETE wave DONE** · rewrite/defer still gated)
**Phase:** 2 · **Type:** hygiene · **Depends:** WO-P2-020 (session package exists)
**Canon:** `canon/architecture/north-star.md` · `canon/findings.md` (AI-pilot / EV-picker divergences)

**Goal:** Stop the silent dead suite. Catalog every root `tests/test_*.py` that still imports the
retired `twclient` package (uncollectable under greenfield) into **rewrite · delete · defer**
buckets so Phase-2 work orders can schedule honest proof instead of drowning in collection ERRORS.

**Progress:** inventory ACCEPTED (`7e75677`) · DELETE wave executed (12 files removed — see §DELETE).
**Still gated:** rewrite / defer execution until a lifting HANDOFF. No `session/login.py` (WO-P2-023).

---

## Failure mode (reproduced 2026-07-24)

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m pytest --collect-only -q
# → Interrupted: 78 errors during collection
# Representative:
#   tests/test_session.py:11: ModuleNotFoundError: No module named 'twclient'
```

Greenfield package is `tw2002_aiclient` (+ `tw2002_aiclient.session.*`). The pre-rebirth
`twclient` package lives only under `archive/pre-rebirth-2026-07-23/code/` and is **not**
importable. Any test that `import twclient` / `from twclient…` fails at **collection**, so
`pytest` never reaches the green subset unless files are ignored or rewritten.

### Collectable today (6) — keep / already greenfield

| File | Note |
|------|------|
| `tests/test_classify.py` | `tw2002_aiclient.session.classify` |
| `tests/test_cli_run_dir.py` | WO-P2-021 |
| `tests/test_ensure_from_play.py` | WO-P2-020 |
| `tests/test_ensure_no_auto_arm.py` | WO-P2-022 |
| `tests/test_env.py` | WO-P2-021 |
| `tests/test_settle.py` | settle baseline |

---

## Bucket rules

| Bucket | Meaning |
|--------|---------|
| **rewrite** | Port imports to `tw2002_aiclient.session.*` (or package root) when the module already exists or a near Phase-2 WO owns it. Prefer verify-first + thin new proofs over wholesale archive restore. |
| **delete** | Pre-rebirth AI-pilot / learning-loop / autonomy-HUD coverage that **contradicts** north-star (AI never live-drives; no EV-every-tick driver). Do not rewrite onto greenfield. |
| **defer** | Archive-only product surface (world model, trade, spectate, crawl, …) with no live module yet — keep file as reference until the owning product WO lands; then rewrite or delete under that WO. |

**Counts (post-DELETE wave):** rewrite **16** · delete **0 remaining** (12 removed) · defer **50** ·
collectable **6** · remaining uncollectable ≈ **66** · total `test_*.py` **72**.

---

## REWRITE (16) — live or Phase-2-near `session.*`

| File | Target / trigger |
|------|------------------|
| `tests/test_connection.py` | `session.connection` (live) |
| `tests/test_credentials.py` | `session.credentials` (live; secrets-lane — coordinate / Max if touching password paths) |
| `tests/test_logging_util.py` | `session.logging_util` (live) |
| `tests/test_session.py` | `session.session` (live) |
| `tests/test_terminal.py` | `session.terminal` (live) |
| `tests/test_iac.py` | `session.iac` (live) |
| `tests/test_player_bank.py` | `session.player_bank` (live) |
| `tests/test_control_lock.py` | `session` control_lock when WO-P2-025 lands (or thin stub today) |
| `tests/test_actor_attribution.py` | protocol + control_lock actor tags (P2-025 adjacent) |
| `tests/test_tw04_toctou.py` | control_lock TOCTOU — fold with P2-025 |
| `tests/test_attach_protocol.py` | attach / human hold — after control_lock + play attach WO |
| `tests/test_attach_redaction.py` | redaction sink + attach path (secrets doctrine) |
| `tests/test_ensure_protocol.py` | overlap with green `test_ensure_from_play` — merge or thin rewrite |
| `tests/test_cli_log.py` | `session.cli` log verb (if retained) |
| `tests/test_login.py` | **WO-P2-023** (CC exclusive until Accept) |
| `tests/test_login_redaction.py` | follow 023 / redaction proofs |

---

## DELETE (12) — DONE (WO-TEST-REHAB-DELETE)

Removed from root `tests/` (north-star contradict / retired AI-first). Archive still holds the
pre-rebirth sources under `archive/pre-rebirth-2026-07-23/code/tests/` for reference.

| File | Why |
|------|-----|
| ~~`tests/test_autopilot.py`~~ | AI-pilot / EV tick loop — findings §1–2 |
| ~~`tests/test_autopilot_protocol.py`~~ | same |
| ~~`tests/test_loop_player.py`~~ | auto-loop driver |
| ~~`tests/test_priority_engine.py`~~ | EV-every-tick picker — findings §2 |
| ~~`tests/test_coach_kb.py`~~ | coach-as-live-driver framing |
| ~~`tests/test_credits_supervision.py`~~ | AI-pilot credits supervisor |
| ~~`tests/test_active_driver.py`~~ | `MODE_AI_PILOT` / skills active-driver |
| ~~`tests/test_learning_candidates.py`~~ | learning-loop (no on-demand Analyze WO yet) |
| ~~`tests/test_learning_comparator.py`~~ | same |
| ~~`tests/test_learning_guards.py`~~ | same |
| ~~`tests/test_learning_loop.py`~~ | same |
| ~~`tests/test_spectate_autonomy_ledger.py`~~ | autonomy-ratio AI HUD |

---

## DEFER (50) — wait for owning product WO

Grouped by pattern (individual files listed).

### CLI verbs not in reborn `session.cli` yet (4)

`tests/test_cli_crawl_wiring.py` · `tests/test_cli_haggle_wiring.py` · `tests/test_cli_menumap.py` · `tests/test_cli_players.py`

### Play / spectate / TUI chrome (pre-cockpit port) (8)

`tests/test_aiclient_adapters.py` · `tests/test_aiclient_play_panels.py` · `tests/test_control_panel.py` · `tests/test_interactive_app.py` · `tests/test_intervention_labels.py` · `tests/test_spectate_app.py` · `tests/test_spectate_layout.py` · `tests/test_clean_preempt.py`

### World / trade / explore / formations (9)

`tests/test_world_model.py` · `tests/test_world_model_integration.py` · `tests/test_world_identity.py` · `tests/test_chains.py` · `tests/test_trade_adapter.py` · `tests/test_trade_driver.py` · `tests/test_explore.py` · `tests/test_formations.py` · `tests/test_fighter_toll_policy.py`

### Game knowledge / data / crawl / menus (11)

`tests/test_game_data.py` · `tests/test_game_data_persist.py` · `tests/test_game_knowledge.py` · `tests/test_game_knowledge_learned_rules.py` · `tests/test_crawl_driver.py` · `tests/test_crawl_start_protocol.py` · `tests/test_menu_crawler.py` · `tests/test_menu_map_view.py` · `tests/test_menu_nav.py` · `tests/test_menu_sig.py` · `tests/test_hud_seed.py`

### Protocol / ledger / skills / watch / misc archive (18)

`tests/test_analyze.py` · `tests/test_frame_recorder.py` · `tests/test_guardian.py` · `tests/test_haggle.py` · `tests/test_integration_introspect_persist.py` · `tests/test_introspector.py` · `tests/test_ledger.py` · `tests/test_miner.py` · `tests/test_name_bank.py` · `tests/test_probe.py` · `tests/test_protocol_haggle.py` · `tests/test_protocol_trainer_panel.py` · `tests/test_replay_ledger_integration.py` · `tests/test_servers.py` · `tests/test_ship_upgrade_decision.py` · `tests/test_skills.py` · `tests/test_state_parser.py` · `tests/test_watch.py`

---

## Suggested execute slices (later HANDOFFs)

1. ~~**Delete wave**~~ — DONE (WO-TEST-REHAB-DELETE).
2. **Rewrite wave A** — connection / logging_util / session / terminal / iac / player_bank (modules live today).
3. **Rewrite wave B** — control_lock + actor/TOCTOU/attach with WO-P2-025.
4. **Login** — leave to WO-P2-023 (+ redaction follow-on).
5. **Defer** — only reopen when the owning product WO lands.

**Accept (inventory):** this file enumerates all 78 uncollectable tests with a bucket · cites collection `ModuleNotFoundError: twclient` · no product edits · scoped commit · STATUS.

**Proof:**
```bash
.venv/bin/python -m pytest --collect-only -q 2>&1 | tail -5
# still 78 ERRORS until a later execute slice; inventory is the deliverable
test -f workorders/WO-TEST-SUITE-REHAB.md
```
