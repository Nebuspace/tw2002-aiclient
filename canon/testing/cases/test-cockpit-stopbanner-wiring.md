---
type: Reference
title: Test Cases — Cockpit Stopbanner Wiring
description: WO-P5-064 Layer-B -- the STOP banner's REGION geometry (``cockpit.
resource: repo://tw2002-aiclient/tests/test_cockpit_stopbanner_wiring.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_stopbanner_wiring.py`

_WO-P5-064 Layer-B -- the STOP banner's REGION geometry (``cockpit._

| Test | Blurb |
|------|-------|
| `test_no_halt_leaves_every_pre_wo_region_untouched` | The banner is opt-in: with ``needs_attention`` unset (the default,. |
| `test_too_small_still_refuses_and_allocates_no_banner` | Too small still refuses and allocates no banner. |
| `test_banner_claims_rows_without_ever_shrinking_logs` | The hazard this WO was warned about, pinned: LOGS must never lose a. |
| `test_banner_is_full_inner_width_directly_above_the_control_strip` | Banner is full inner width directly above the control strip. |
| `test_no_region_overlaps_or_escapes_the_frame_at_a_halt` | No region overlaps or escapes the frame at a halt. |
| `test_banner_height_is_the_three_band_constant_when_there_is_room` | Banner height is the three band constant when there is room. |
| `test_the_banner_costs_the_center_viewport_rows_only_below_37_lines` | Honest statement of what the banner DOES take, so a future change. |
| `test_the_banner_outranks_the_control_strip_under_height_pressure` | Canon's safety-legibility invariant (``mode-line-and-teach-. |
| `test_halt_paints_all_three_bands_on_the_banner_rows` | Halt paints all three bands on the banner rows. |
| `test_teach_affordances_are_visible_on_screen_at_a_halt` | Teach affordances are visible on screen at a halt. |
| `test_unknown_code_reaches_the_screen_raw_with_no_invented_prose` | Unknown code reaches the screen raw with no invented prose. |
| `test_banner_rows_carry_the_warn_bold_weight` | Canon: the strip is painted warn-tone AND bold. |
| `test_no_halt_paints_no_banner_and_leaves_the_bottom_stack_where_it_was` | No halt paints no banner and leaves the bottom stack where it was. |
| `test_a_raising_banner_composer_never_crashes_the_draw_pass` | A raising banner composer never crashes the draw pass. |
| `test_a_raising_needs_attention_gate_degrades_to_the_calm_layout` | A raising needs attention gate degrades to the calm layout. |
| `test_exactly_one_status_poll_per_draw_halt_or_not` | Exactly one status poll per draw halt or not. |
| `test_a_raising_status_provider_still_draws_the_calm_frame` | A raising status provider still draws the calm frame. |
