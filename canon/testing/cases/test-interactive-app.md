---
type: Reference
title: Test Cases — Interactive App
description: pty regression test for `tw attach`'s interactive keystroke-routing +.
resource: repo://tw2002-aiclient/tests/test_interactive_app.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_interactive_app.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_pty regression test for `tw attach`'s interactive keystroke-routing +_

| Test | Blurb |
|------|-------|
| `test_attach_forwards_a_real_keystroke_through_a_pty` | Attach forwards a real keystroke through a pty. |
| `test_attach_status_bar_echoes_the_tx_of_the_last_key_sent` | Core transparency's TX readout in MANUAL mode -- tracked LOCALLY. |
| `test_attach_caret_tracks_the_reported_cursor_position` | motion F2: a visible caret at the game's own cursor position, not. |
| `test_ctrl_bracket_detaches_and_releases_the_control_lock` | Ctrl bracket detaches and releases the control lock. |
| `test_second_attach_is_rejected_while_pty_session_is_active` | Proves the rejection surfaces BEFORE curses ever takes over the. |
