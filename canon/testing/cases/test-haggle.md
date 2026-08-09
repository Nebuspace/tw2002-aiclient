---
type: Reference
title: Test Cases — test_haggle
description: Haggle.
resource: repo://tw2002-aiclient/tests/test_haggle.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_haggle.py`

_Haggle._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_run_haggle_buy_direction_converges_in_two_rounds_like_the_real_capture` | Run haggle buy direction converges in two rounds like the real capture. |
| `test_run_haggle_sell_direction_converges_in_two_rounds_like_the_real_capture` | Run haggle sell direction converges in two rounds like the real capture. |
| `test_run_haggle_accepts_immediately_if_the_port_takes_the_opening_ask_outright` | Run haggle accepts immediately if the port takes the opening ask outright. |
| `test_run_haggle_concedes_toward_midpoint_when_not_yet_within_threshold` | Run haggle concedes toward midpoint when not yet within threshold. |
| `test_run_haggle_round_cap_fallback_when_the_port_never_converges` | Run haggle round cap fallback when the port never converges. |
| `test_run_haggle_desync_fallback_when_the_screen_goes_unrecognized` | Run haggle desync fallback when the screen goes unrecognized. |
| `test_run_haggle_no_active_haggle_when_dispatched_off_context` | Run haggle no active haggle when dispatched off context. |
| `test_run_haggle_honors_an_explicit_fair_value_override` | Run haggle honors an explicit fair value override. |
| `test_run_haggle_stale_command_prompt_elsewhere_on_screen_does_not_confirm_a_deal` | Run haggle stale command prompt elsewhere on screen does not confirm a deal. |
| `test_run_haggle_stray_content_after_the_accept_default_send_does_not_confirm_a_deal` | Run haggle stray content after the accept default send does not confirm a deal. |
| `test_run_haggle_reports_the_verified_credits_delta_as_final_price_over_a_guessed_ask` | Run haggle reports the verified credits delta as final price over a guessed ask. |
| `test_run_haggle_waits_for_a_fresh_settled_render_before_reading_the_opening_prompt` | Run haggle waits for a fresh settled render before reading the opening prompt. |
| `test_run_haggle_bare_command_prompt_only_after_ask_is_desync_fallback` | Run haggle bare command prompt only after ask is desync fallback. |
| `test_run_haggle_bare_command_prompt_only_after_accept_default_is_desync_fallback` | Run haggle bare command prompt only after accept default is desync fallback. |
| `test_run_haggle_sector_header_plus_command_is_desync_fallback` | Run haggle sector header plus command is desync fallback. |
| `test_run_haggle_desync_fallback_when_the_screen_never_settles_before_the_first_read` | Run haggle desync fallback when the screen never settles before the first read. |
