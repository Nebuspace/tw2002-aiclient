---
type: Reference
title: Test Cases — Login Resume
description: Login Automaton idempotent-resume proof (WO-P2-024): drives the REAL.
resource: repo://tw2002-aiclient/tests/test_login_resume.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_login_resume.py`

_Login Automaton idempotent-resume proof (WO-P2-024): drives the REAL_

| Test | Blurb |
|------|-------|
| `test_resume_from_door_select_reaches_main_command` | Resume from door select reaches main command. |
| `test_resume_from_interstitial_reaches_main_command` | Resume from interstitial reaches main command. |
| `test_no_double_answer_after_stale_game_select_redraw` | No double answer after stale game select redraw. |
| `test_second_run_login_is_idempotent_at_main_command` | Second run login is idempotent at main command. |
