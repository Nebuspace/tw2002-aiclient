---
type: Reference
title: Test Cases — test_attach_redaction
description: Attach keystroke secret redaction (WO-P2-OPS-VERB-F1b).
resource: repo://tw2002-aiclient/tests/test_attach_redaction.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_attach_redaction.py`

_Attach keystroke secret redaction (WO-P2-OPS-VERB-F1b)._

| Test | Blurb |
|------|-------|
| `test_password_prompt_sentinel_never_leaks_in_log_or_last_sent` | Password prompt sentinel never leaks in log or last sent. |
| `test_falsification_removing_log_gate_lets_sentinel_leak` | Falsification removing log gate lets sentinel leak. |
| `test_pin_prompt_sentinel_never_leaks` | Pin prompt sentinel never leaks. |
| `test_ordinary_command_prompt_is_not_redacted` | Ordinary command prompt is not redacted. |
| `test_documented_residual_no_secret_keyword_not_redacted` | Documented residual no secret keyword not redacted. |
| `test_staleness_secret_during_fence_wait_still_redacted` | Staleness secret during fence wait still redacted. |
| `test_attach_secret_never_reaches_the_status_verbs_whole_json_response` | Attach secret never reaches the status verbs whole json response. |
| `test_attach_ordinary_keystrokes_do_reach_the_status_verbs_log_tail` | Attach ordinary keystrokes do reach the status verbs log tail. |
