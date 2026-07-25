---
type: Reference
title: Test Cases — Cockpit Arm Wiring
description: WO-P5-062 Layer-B -- the ARM indicator's placement in the control strip.
resource: repo://tw2002-aiclient/tests/test_cockpit_arm_wiring.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_arm_wiring.py`

_WO-P5-062 Layer-B -- the ARM indicator's placement in the control strip_

| Test | Blurb |
|------|-------|
| `test_every_seat_and_arm_combination_renders_both_chips` | All nine combinations, including the three the WO calls out as the. |
| `test_the_arm_reading_is_unmoved_by_every_seat_state` | Independence, direction one: hold the daemon's report fixed, walk. |
| `test_the_seat_reading_is_unmoved_by_every_arm_state` | Independence, direction two -- the mirror, which matters just as. |
| `test_arm_reads_a_different_input_than_the_seat_badge_entirely` | The structural root of the independence above: the seat badge is. |
| `test_lock_state_words_never_appear_in_any_arm_label` | ARM ! |
| `test_no_key_and_no_seat_transition_can_make_the_indicator_read_armed` | Accept #3, behaviourally. |
| `test_that_assertion_is_not_vacuous_only_the_daemons_report_can_arm` | The companion without which the test above proves nothing. |
| `test_the_chip_only_ever_sees_the_object_the_status_provider_returned` | The structural half of Accept #3: the cockpit cannot fabricate an. |
| `test_the_cockpit_holds_no_arm_state_of_its_own` | There is nothing to flip. |
| `test_a_dropped_status_poll_degrades_to_unknown_never_to_a_calm_disarmed` | The failure mode with real consequences: the daemon goes away. |
| `test_a_raising_status_provider_shows_unknown_rather_than_a_calm_claim` | A raising status provider shows unknown rather than a calm claim. |
| `test_the_arm_chip_lands_immediately_right_of_the_seat_chip` | The arm chip lands immediately right of the seat chip. |
| `test_the_liveness_cluster_still_survives_beside_both_chips` | The strip's pre-existing, operationally load-bearing "is it. |
| `test_the_armed_chip_carries_the_badge_attributes` | Canon's badge law (``mode-line-and-teach-controls. |
| `test_the_disarmed_chip_stays_calm_and_unbadged` | The muted register ``SPECTATE`` already establishes on this row:. |
| `test_a_raising_arm_composer_never_crashes_the_draw_pass` | A raising arm composer never crashes the draw pass. |
| `test_omitting_the_arm_chip_is_byte_identical_to_the_pre_wo_row` | Backward compatibility, structurally: with no arm chip supplied the. |
| `test_the_row_is_still_exactly_width_characters_with_the_arm_chip_present` | The invariant every caller of this row depends on. |
| `test_line_and_segments_stay_byte_identical_with_an_arm_chip` | The concatenation invariant PWO-060 established, extended to the. |
| `test_the_arm_chip_is_all_or_nothing_never_truncated` | The width-pressure safety property. |
| `test_the_seat_chip_outranks_the_arm_chip_under_width_pressure` | Canon (``mode-line-and-teach-controls. |
| `test_the_arm_chip_renders_even_when_the_seat_makes_no_claim` | Independence at the composer layer, in the case that would be. |
| `test_a_malformed_arm_chip_degrades_to_no_chip_and_never_raises` | House hardening discipline: every public composer here is. |
| `test_an_unknown_arm_tone_degrades_to_plain_rather_than_dropping_the_chip` | A tone outside the draw layer's vocabulary must not cost the. |
| `test_exactly_one_status_poll_per_draw_with_the_arm_chip_wired` | The arm chip is a new consumer of the shared per-draw snapshot; it. |
| `test_control_seat_still_never_reads_the_daemon_status_itself` | ``control_seat``'s module docstring commits at length to never. |
