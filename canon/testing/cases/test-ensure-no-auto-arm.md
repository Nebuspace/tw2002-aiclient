---
type: Reference
title: Test Cases — test_ensure_no_auto_arm
description: WO-P2-022 — ensure never surprise-arms App autopilot.
resource: repo://tw2002-aiclient/tests/test_ensure_no_auto_arm.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_ensure_no_auto_arm.py`

_WO-P2-022 — ensure never surprise-arms App autopilot._

| Test | Blurb |
|------|-------|
| `test_parser_accepts_no_auto_arm_flag` | Parser accepts no auto arm flag. |
| `test_parser_bare_ensure_defaults_no_auto_arm_false` | Flag default is False, but runtime still never arms (WO-P2-022). |
| `test_ensure_raw_forwards_no_auto_arm_on_wire` | Ensure raw forwards no auto arm on wire. |
| `test_adapters_ensure_session_forwards_no_auto_arm` | Adapters ensure session forwards no auto arm. |
| `test_dispatch_ensure_never_arms_even_when_profile_would` | Bare ensure with autopilot-ish profile metadata still only logs in / returns already_there — no autopilot loop start side effect. |
| `test_status_json_reports_autopilot_not_running` | WO-P2-022 Accept: after ensure, status --json shows App not driving. |
