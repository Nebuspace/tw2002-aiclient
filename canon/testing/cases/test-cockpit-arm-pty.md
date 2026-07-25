---
type: Reference
title: Test Cases — Cockpit Arm Pty
description: WO-P5-062 Accept #4 -- the ARM indicator on a real terminal.
resource: repo://tw2002-aiclient/tests/test_cockpit_arm_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_arm_pty.py`

_WO-P5-062 Accept #4 -- the ARM indicator on a real terminal._

| Test | Blurb |
|------|-------|
| `test_the_arm_indicator_is_visible_on_a_real_terminal` | Accept #4. |
| `test_the_seat_chip_and_the_arm_chip_are_both_visible_on_the_same_row` | Accept #1 at the terminal: the two facts sit side by side on one. |
| `test_a_daemon_reporting_disarmed_renders_the_disarmed_chip` | The reading a live daemon produces today -- ``session/protocol. |
| `test_only_the_daemons_own_report_can_put_armed_on_a_real_screen` | Accept #2 and the TTY-layer non-vacuity companion for Accept #3. |
| `test_the_seat_chip_is_unmoved_by_the_daemons_arm_report` | The hazard, proved end to end on a real terminal: ARM is not the. |
