---
type: Reference
title: Test Cases — test_play_chrome_nav
description: WO-P3-030 — Play-chrome navigation (Esc → launcher, daemon survives).
resource: repo://tw2002-aiclient/tests/test_play_chrome_nav.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_play_chrome_nav.py`

_WO-P3-030 — Play-chrome navigation (Esc → launcher, daemon survives)._

| Test | Blurb |
|------|-------|
| `test_module_imports_tw2002_aiclient_only` | Module imports tw2002 aiclient only. |
| `test_play_shell_esc_returns_back_router_token` | Play shell esc returns back router token. |
| `test_run_play_esc_returns_back_without_stopping_fake_session` | Daemon-survival leg: Esc ends the binding; FakeSession stays alive. |
| `test_esc_from_play_shell_returns_launcher_without_exit` | Layer-B Accept: Enter → handle visible; Esc → launcher; no process exit mid-nav. |
