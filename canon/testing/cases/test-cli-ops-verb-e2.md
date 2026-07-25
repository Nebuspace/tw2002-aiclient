---
type: Reference
title: Test Cases — Cli Ops Verb E2
description: WO-P2-OPS-VERB-E2 — ``tw watch`` NDJSON / settle-edge tail over subscribe.
resource: repo://tw2002-aiclient/tests/test_cli_ops_verb_e2.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cli_ops_verb_e2.py`

_WO-P2-OPS-VERB-E2 — ``tw watch`` NDJSON / settle-edge tail over subscribe._

| Test | Blurb |
|------|-------|
| `test_parser_lists_watch` | Parser lists watch. |
| `test_cmd_watch_daemon_not_running` | Cmd watch daemon not running. |
| `test_cmd_watch_prints_seed_then_stops_at_frames` | Fake unix peer: one subscribe request → two NDJSON events, then EOF. |
