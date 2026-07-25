---
type: Reference
title: Test Cases — Cockpit Goals Pty
description: WO-P3-034 wire — GOALS panel + 1 Hz status_provider refresh, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_goals_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_goals_pty.py`

_WO-P3-034 wire — GOALS panel + 1 Hz status_provider refresh, Layer-B._

| Test | Blurb |
|------|-------|
| `test_goals_title_visible_above_focus` | Goals title visible above focus. |
| `test_no_provider_run_shows_all_unknown_honest_lines` | No status_provider data (real transport, empty isolated run dir):. |
| `test_stubbed_provider_shows_known_credits_label_and_value` | Stubbed provider shows known credits label and value. |
| `test_daemon_status_provider_uses_a_bounded_poll_timeout` | HIGH: the GOALS poll must pass an explicit short timeout, never. |
| `test_draw_survives_a_raising_compose_goals_lines` | Defense-in-depth: ``draw()`` already guarded the ``status_provider()``. |
| `test_inf_credits_status_survives_and_esc_still_exits` | Mack's exact end-to-end repro, paired proof: a stubbed status of. |
