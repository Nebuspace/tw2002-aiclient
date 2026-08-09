---
type: Reference
title: Test Cases — test_aiclient_adapters
description: REMOVED — historical inventory; tip module absent. Unit tests for tw2002_aiclient ensure/autopilot adapters (mocked daemon).
resource: repo://tw2002-aiclient/tests/test_aiclient_adapters.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_aiclient_adapters.py`

_Unit tests for tw2002_aiclient ensure/autopilot adapters (mocked daemon)._

> **REMOVED** — module absent on tip (not merely pytest-ignored). Catalogued for completeness (historical inventory).
| Test | Blurb |
|------|-------|
| `test_resolve_run_dir_defaults_to_shared_run` | Resolve run dir defaults to shared run. |
| `test_resolve_run_dir_honors_tw_run_dir_env` | Resolve run dir honors tw run dir env. |
| `test_resolve_run_dir_explicit_wins_over_env` | Resolve run dir explicit wins over env. |
| `test_default_run_dir_for_profile_aliases_resolve` | Default run dir for profile aliases resolve. |
| `test_ensure_and_sync_autopilot_off_stops_trainer` | Ensure and sync autopilot off stops trainer. |
| `test_ensure_and_sync_autopilot_on_arms_trainer` | Ensure and sync autopilot on arms trainer. |
| `test_ensure_and_sync_propagates_ensure_failure` | Ensure and sync propagates ensure failure. |
| `test_toggle_autopilot_and_sync_on` | Toggle autopilot and sync on. |
| `test_list_launcher_rows_active_first_and_marks_retired` | List launcher rows active first and marks retired. |
| `test_list_launcher_rows_omitted_retired_is_active` | List launcher rows omitted retired is active. |
| `test_launcher_selectable_skips_retired` | Launcher selectable skips retired. |
| `test_launcher_step_skips_retired_rows` | Launcher step skips retired rows. |
| `test_run_attach_delegates_to_interactive_app` | Thin wrap: configure run_dir, hand sock/pid to interactive_app. |
| `test_run_attach_stops_running_autopilot_before_attach` | Play attach with AP ON: stop runtime trainer, then take MODE_HUMAN. |
| `test_run_attach_surfaces_autopilot_stop_failure` | Run attach surfaces autopilot stop failure. |
| `test_run_attach_reports_daemon_not_running` | Run attach reports daemon not running. |
| `test_suspend_and_attach_restores_curses` | Play-screen suspend idiom: endwin → attach → reset, never raise. |
| `test_suspend_and_attach_surfaces_failure_and_still_restores` | Suspend and attach surfaces failure and still restores. |
| `test_create_form_fields_have_no_password` | Create form fields have no password. |
| `test_save_form_creates_profile_without_password` | Create path writes profiles.toml shape only — never secrets. |
| `test_adapter_create_profile_refuses_password_kwarg` | Adapter create profile refuses password kwarg. |
| `test_operator_doc_documents_password_defer` | Operator doc documents password defer. |
| `test_operator_doc_attach_stops_runtime_autopilot` | WO-OPERATOR-DOC-ATTACH-STOP: cold-start attach matches ATTACH-STOPS. |
| `test_operator_doc_warp_confirm_recovery_row` | WO-OPERATOR-DOC-WARP-CONFIRM: live-seat signature + recover steps. |
