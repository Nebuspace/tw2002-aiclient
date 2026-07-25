---
type: Reference
title: Test Cases — Cli Attach Keys Exit Code
description: WO-AUDIT-CLI-KEYS-IGNORE-RETURN — ``tw attach --keys`` must not report.
resource: repo://tw2002-aiclient/tests/test_cli_attach_keys_exit_code.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cli_attach_keys_exit_code.py`

_WO-AUDIT-CLI-KEYS-IGNORE-RETURN — ``tw attach --keys`` must not report_

| Test | Blurb |
|------|-------|
| `test_cmd_attach_keys_failed_send_is_non_zero_and_reported` | Cmd attach keys failed send is non zero and reported. |
| `test_cmd_attach_keys_successful_send_still_returns_zero` | Cmd attach keys successful send still returns zero. |
| `test_cmd_attach_keys_empty_string_sends_nothing_and_returns_zero` | Pre-existing behavior, preserved deliberately: ``--keys ""`` decodes. |
