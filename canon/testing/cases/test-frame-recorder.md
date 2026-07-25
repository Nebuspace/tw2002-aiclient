---
type: Reference
title: Test Cases — test_frame_recorder
description: WO-FRAMES-0 — frame recorder + build_response hook + CLI read path.
resource: repo://tw2002-aiclient/tests/test_frame_recorder.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_frame_recorder.py`

_WO-FRAMES-0 — frame recorder + build_response hook + CLI read path._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_last_nonblank_prefers_qty_over_blank_pad` | Last nonblank prefers qty over blank pad. |
| `test_recorder_appends_and_grows` | Recorder appends and grows. |
| `test_grep_finds_qty_line` | Grep finds qty line. |
| `test_diff_shows_line_delta` | Diff shows line delta. |
| `test_secret_sent_input_redacted` | Secret sent input redacted. |
