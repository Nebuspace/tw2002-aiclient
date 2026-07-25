---
type: Reference
title: Test Cases — test_cli_run_dir
description: WO-P2-021 — CLI / daemon run-dir wiring against the reborn session API.
resource: repo://tw2002-aiclient/tests/test_cli_run_dir.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cli_run_dir.py`

_WO-P2-021 — CLI / daemon run-dir wiring against the reborn session API._

| Test | Blurb |
|------|-------|
| `test_resolve_run_dir_default` | Resolve run dir default. |
| `test_resolve_run_dir_relative` | Resolve run dir relative. |
| `test_resolve_run_dir_absolute` | Resolve run dir absolute. |
| `test_parser_default_run_dir_none` | Parser default run dir none. |
| `test_parser_run_dir_on_status` | Parser run dir on status. |
| `test_parser_run_dir_on_ensure` | Parser run dir on ensure. |
| `test_send_request_uses_resolved_run_dir` | Send request uses resolved run dir. |
| `test_cmd_status_includes_run_dir_when_daemon_down` | Cmd status includes run dir when daemon down. |
| `test_ensure_raw_propagates_tw_run_dir_to_spawn_env` | Daemon spawn must pass TW_RUN_DIR in the child env (not argv). |
| `test_claim_pidfile_refuses_live_holder` | WO-P2-021 Accept #3: pidfile guard holds independently per run-dir. |
| `test_claim_pidfile_replaces_stale` | Claim pidfile replaces stale. |
| `test_default_has_no_per_profile_splinter` | Default has no per profile splinter. |
