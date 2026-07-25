---
type: Reference
title: Test Cases — test_connection
description: TelnetConnection unit tests — no network.
resource: repo://tw2002-aiclient/tests/test_connection.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_connection.py`

_TelnetConnection unit tests — no network._

| Test | Blurb |
|------|-------|
| `test_send_bytes_secret_false_logs_raw_bytes` | Send bytes secret false logs raw bytes. |
| `test_send_bytes_secret_true_redacts_the_log_line` | Send bytes secret true redacts the log line. |
| `test_send_bytes_secret_true_still_sends_the_real_bytes_over_the_wire` | Send bytes secret true still sends the real bytes over the wire. |
| `test_send_text_secret_true_redacts_the_log_line` | Send text secret true redacts the log line. |
| `test_send_text_appends_crlf_by_default` | Send text appends crlf by default. |
| `test_send_text_enter_false_sends_exact_bytes` | Send text enter false sends exact bytes. |
| `test_send_bytes_with_no_logger_never_raises` | Send bytes with no logger never raises. |
