---
type: Reference
title: Test Cases — Control Panel
description: pty regression tests for the Trainer Control Panel's REAL keypress-.
resource: repo://tw2002-aiclient/tests/test_control_panel.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_control_panel.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_pty regression tests for the Trainer Control Panel's REAL keypress-_

| Test | Blurb |
|------|-------|
| `test_pressing_m_cycles_ai_pilot_to_spectate_and_back` | Pressing m cycles ai pilot to spectate and back. |
| `test_pressing_p_panics_and_stops_a_running_loop` | Pressing p panics and stops a running loop. |
| `test_library_browse_select_and_enter_starts_the_loop` | The full Learned-Loops Library flow: L opens it, the real. |
| `test_library_enter_alone_does_not_start_the_loop_on_the_daemon` | The other half of the confirm-gate proof, against the REAL daemon. |
| `test_x_stops_a_running_loop_and_returns_to_ai_pilot` | X stops a running loop and returns to ai pilot. |
| `test_space_pauses_and_resumes_a_running_loop` | Space pauses and resumes a running loop. |
