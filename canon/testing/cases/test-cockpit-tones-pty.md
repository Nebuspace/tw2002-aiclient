---
type: Reference
title: Test Cases — Cockpit Tones Pty
description: WO-P3-040 wire — semantic chrome tones, Layer-B.
resource: repo://tw2002-aiclient/tests/test_cockpit_tones_pty.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_tones_pty.py`

_WO-P3-040 wire — semantic chrome tones, Layer-B._

| Test | Blurb |
|------|-------|
| `test_full_tier_viewport_border_default_chrome_tone_matches_tones_table` | Full tier viewport border default chrome tone matches tones table. |
| `test_disconnected_status_flips_viewport_border_to_danger_non_bold` | Disconnected status flips viewport border to danger non bold. |
| `test_status_missing_connected_field_leaves_viewport_border_chrome_cyan` | Status missing connected field leaves viewport border chrome cyan. |
| `test_no_daemon_at_all_leaves_viewport_border_chrome_cyan` | No daemon at all leaves viewport border chrome cyan. |
| `test_ascii_mode_disconnected_flip_same_tone_as_unicode_mode` | Ascii mode disconnected flip same tone as unicode mode. |
| `test_pty_viewport_border_returns_to_identical_chrome_cell_after_reconnect` | The border must return to the IDENTICAL rendered cyan cell after a. |
| `test_play_shell_screen_handle_key_unchanged_esc_and_q_only` | Play shell screen handle key unchanged esc and q only. |
| `test_poll_guard_fires_exactly_once_at_full_tier_with_viewport_border` | Poll guard fires exactly once at full tier with viewport border. |
| `test_viewport_border_attr_non_dict_status_stays_chrome` | Viewport border attr non dict status stays chrome. |
| `test_viewport_border_attr_non_bool_connected_stays_chrome` | Viewport border attr non bool connected stays chrome. |
| `test_viewport_border_attr_hostile_idle_ms_never_raises_and_stays_ok` | Viewport border attr hostile idle ms never raises and stays ok. |
| `test_viewport_border_attr_disconnected_returns_danger_attr` | Viewport border attr disconnected returns danger attr. |
| `test_viewport_border_attr_stale_but_connected_stays_chrome_not_danger` | status_semantic's "warn" tone (connected but stale) must NOT flip the. |
| `test_viewport_border_attr_round_trips_cyan_danger_cyan_on_reconnect` | Viewport border attr round trips cyan danger cyan on reconnect. |
| `test_viewport_border_attr_survives_five_cycle_oscillation` | A "flips once then latches" bug could still survive a single round. |
| `test_shared_pair_exhaustion_reproduces_and_is_fixed_by_underline_interim` | Empirical probe: with a small, deterministic COLOR_PAIRS ceiling (3). |
| `test_danger_only_allocation_failure_still_gets_underline_interim` | REVISE (team-lead, WO-P4-054): a narrower ``danger == chrome`` guard. |
| `test_chrome_and_danger_attrs_are_never_equal_guard` | Required regardless of whether exhaustion reproduces on any given. |
| `test_launcher_row_colors_survive_a_play_shell_round_trip` | Mack's CRITICAL PoC, pinned: the SAME LauncherScreen instance's. |
