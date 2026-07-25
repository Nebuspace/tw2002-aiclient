---
type: Reference
title: Test Cases — Play Esc Daemon Survival
description: WO-P3-030 lane 2 — Esc→launcher must NOT tear down the session/daemon.
resource: repo://tw2002-aiclient/tests/test_play_esc_daemon_survival.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_play_esc_daemon_survival.py`

_WO-P3-030 lane 2 — Esc→launcher must NOT tear down the session/daemon._

| Test | Blurb |
|------|-------|
| `test_play_shell_esc_returns_back_not_quit` | Esc ends the TUI binding (``back``); it is not process quit. |
| `test_run_play_source_never_calls_stop` | Static guard: ``_run_play`` body has no stop/teardown call sites. |
| `test_run_play_esc_issues_no_daemon_stop_verb` | Drive Esc through ``_run_play``; assert no ``stop`` wire verb / sock traffic. |
