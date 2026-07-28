# AUDIT — pytest `--ignore` list landmine census (WO-TEST-IGNORE-LIST-LANDMINE-AUDIT)

**Seat:** Cursor (`impl-aiclient-cursor`) · tip of `wo/TEST-IGNORE-LIST-AUDIT`  
**Method:** for each of 39 `--ignore=` paths in `pytest.ini`, ran
`.venv/bin/python -m pytest -n0 --collect-only <file>` (ignore bypassed).  
**Measured:** 2026-07-28T04:31Z · **39/39** present on disk.

## Rollup

| Collect result | Count |
|---|---|
| `COLLECT_OK` (green collect; ignored anyway) | **2** |
| `TWCLIENT` (`ModuleNotFoundError: twclient`) | **36** |
| `STALE_API` (imports `tw2002_aiclient` but missing symbol) | **1** |

Correction vs CC **04:16:48Z** (“37/39 hard-fail on twclient”): **36** hard-fail on
`twclient`; **1** fails first on a deleted `tw2002_aiclient.screens` symbol
(also imports `twclient`); **2** collect cleanly and were false-ignored.

## Disposition key

| Tag | Meaning |
|---|---|
| **UNIGNORE-NOW** | Collects + suite green; remove `--ignore` this WO |
| **BANK-REHAB** | Product surface live; only ignored/archive coverage — bank rewrite WO |
| **BANK-DELETE** | Archive-only API; no reborn product twin worth lifting |
| **KEEP-IGNORED** | Honest bank: daemon/CLI verb or runner not in scope yet |

## Full table

| File | Collect class | Product surface implicated | Disposition |
|---|---|---|---|
| `tests/test_credentials.py` | **COLLECT_OK** | `session.credentials` password mint | **UNIGNORE-NOW** (this WO) |
| `tests/test_world_identity.py` | **COLLECT_OK** | `world_identity` (sole coverage) | **UNIGNORE-NOW** (this WO) · **HIGH landmine** while ignored |
| `tests/test_aiclient_adapters.py` | **STALE_API** (`_launcher_selectable`) | `screens` / launcher adapters | **BANK-REHAB** `WO-TEST-AICLIENT-ADAPTERS-REHAB` |
| `tests/test_aiclient_play_panels.py` | TWCLIENT | archive play panels | **BANK-DELETE** or KEEP until panel port |
| `tests/test_analyze.py` | TWCLIENT | AI analyze (not live-drive) | KEEP-IGNORED / BANK when teacher ported |
| `tests/test_clean_preempt.py` | TWCLIENT | control preempt | BANK-REHAB if fence still product-critical |
| `tests/test_cli_crawl_wiring.py` | TWCLIENT | crawl CLI verb (G2 unwired) | **KEEP-IGNORED** (pytest.ini already documents) |
| `tests/test_cli_haggle_wiring.py` | TWCLIENT | haggle CLI | KEEP-IGNORED until haggle verb |
| `tests/test_cli_players.py` | TWCLIENT | players CLI | KEEP-IGNORED / BANK-DELETE |
| `tests/test_control_panel.py` | TWCLIENT | archive control panel PTY | BANK-DELETE or KEEP |
| `tests/test_crawl_start_protocol.py` | TWCLIENT | crawl protocol (G2 unwired) | **KEEP-IGNORED** |
| `tests/test_fighter_toll_policy.py` | TWCLIENT | policy | BANK-DELETE until policy module |
| `tests/test_formations.py` | TWCLIENT | `explore.plan_find_formations` + cockpit Formations | **BANK-REHAB HIGH** `WO-TEST-FORMATIONS-REHAB` (landmine class — #142 disarmed product; test still ignored) |
| `tests/test_frame_recorder.py` | TWCLIENT | frame recorder | KEEP / BANK-DELETE |
| `tests/test_game_data.py` | TWCLIENT | game_data | BANK-DELETE |
| `tests/test_game_data_persist.py` | TWCLIENT | game_data persist | BANK-DELETE |
| `tests/test_game_knowledge.py` | TWCLIENT | game_knowledge | BANK-DELETE |
| `tests/test_game_knowledge_learned_rules.py` | TWCLIENT | learned rules | BANK-DELETE |
| `tests/test_haggle.py` | TWCLIENT | haggle pure | KEEP until haggle port |
| `tests/test_hud_seed.py` | TWCLIENT | HUD seed | BANK-REHAB → cockpit hud (partial live suite exists) |
| `tests/test_integration_introspect_persist.py` | TWCLIENT | introspect persist | BANK-DELETE |
| `tests/test_interactive_app.py` | TWCLIENT | interactive app PTY | BANK-REHAB MED (overlap with live app tests) |
| `tests/test_intervention_labels.py` | TWCLIENT | intervention labels | BANK-DELETE |
| `tests/test_introspector.py` | TWCLIENT | introspector | BANK-DELETE |
| `tests/test_ledger.py` | TWCLIENT | ledger | KEEP / BANK when ledger ported |
| `tests/test_miner.py` | TWCLIENT | miner | BANK-DELETE |
| `tests/test_name_bank.py` | TWCLIENT | name bank | BANK-DELETE |
| `tests/test_probe.py` | TWCLIENT | probe | BANK-DELETE |
| `tests/test_protocol_haggle.py` | TWCLIENT | protocol haggle | KEEP until verb |
| `tests/test_protocol_trainer_panel.py` | TWCLIENT | trainer panel protocol | BANK-REHAB MED |
| `tests/test_replay_ledger_integration.py` | TWCLIENT | ledger replay | KEEP / BANK |
| `tests/test_servers.py` | TWCLIENT | archive `twclient.servers` | **BANK-DELETE** (reborn: `server_inventory` + credentials `list_servers` already pinned) |
| `tests/test_ship_upgrade_decision.py` | TWCLIENT | ship upgrade | BANK-DELETE |
| `tests/test_skills.py` | TWCLIENT | skills | BANK-DELETE |
| `tests/test_spectate_app.py` | TWCLIENT | spectate app mega-suite | BANK-REHAB LARGE (partial live spectate coverage exists) |
| `tests/test_spectate_layout.py` | TWCLIENT | spectate layout | BANK-REHAB / overlap cockpit layout |
| `tests/test_state_parser.py` | TWCLIENT | `session.state_parser` | **BANK-REHAB HIGH** `WO-TEST-STATE-PARSER-REHAB` (product live; sector-read pins exist but full parser suite ignored) |
| `tests/test_trade_driver.py` | TWCLIENT | autonomous trade runner | **KEEP-IGNORED** (pytest.ini: out of chain-detect scope) |
| `tests/test_world_model_integration.py` | TWCLIENT | world_model I/O | BANK-REHAB MED (`world_model` product live) |

## HIGH landmines banked this WO

1. **`WO-TEST-FORMATIONS-REHAB`** — rewrite `test_formations.py` onto
   `explore.plan_find_formations` / refuse-unavailable pins; un-ignore after green.
2. **`WO-TEST-STATE-PARSER-REHAB`** — port archive `test_state_parser.py` onto
   `tw2002_aiclient.session.state_parser` (or delete after proving live pins supersede).
3. **`WO-TEST-AICLIENT-ADAPTERS-REHAB`** — repair or delete
   `test_aiclient_adapters.py` (`_launcher_selectable` gone).

## Optional small rehab executed here

Removed `--ignore` for `tests/test_credentials.py` and
`tests/test_world_identity.py` (both collected + passed under `-n0`).

## What this does *not* do

No mass-unignore of the 36 `twclient` files. No CHAINS-TUI / `cockpit/chains` edits (#147).
