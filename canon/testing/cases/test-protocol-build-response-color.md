---
type: Reference
title: Test Cases — Protocol Build Response Color
description: WO-P4-053 — ``protocol.
resource: repo://tw2002-aiclient/tests/test_protocol_build_response_color.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_protocol_build_response_color.py`

_WO-P4-053 — ``protocol.build_response()`` color wiring._

| Test | Blurb |
|------|-------|
| `test_bare_path_color_present_and_matches_render_with_color_output` | Bare path color present and matches render with color output. |
| `test_bare_path_calls_render_with_color_exactly_once` | Bare path calls render with color exactly once. |
| `test_bare_path_rows_and_color_are_the_same_capture` | Bare path rows and color are the same capture. |
| `test_bare_path_empty_screen_still_adds_color_key` | Bare path empty screen still adds color key. |
| `test_rows_supplied_path_omits_color_key` | Rows supplied path omits color key. |
| `test_rows_supplied_path_never_calls_render_with_color` | Rows supplied path never calls render with color. |
| `test_rows_supplied_path_with_extra_and_settled_reason_still_omits_color` | Rows supplied path with extra and settled reason still omits color. |
| `test_rows_supplied_empty_list_still_omits_color` | Rows supplied empty list still omits color. |
| `test_wire_send_verb_bare_path_carries_color` | Wire send verb bare path carries color. |
| `test_wire_screen_raw_verb_omits_color_and_skips_render_with_color` | Wire screen raw verb omits color and skips render with color. |
| `test_wire_screen_non_raw_verb_carries_color` | Wire screen non raw verb carries color. |
