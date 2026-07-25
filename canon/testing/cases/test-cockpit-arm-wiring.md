---
type: Reference
title: Test Cases — test_cockpit_arm_wiring
description: Cockpit arm wiring.
resource: repo://tw2002-aiclient/tests/test_cockpit_arm_wiring.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_arm_wiring.py`

_Cockpit arm wiring._

| Test | Blurb |
|------|-------|
| `test_every_seat_and_arm_combination_renders_both_chips` | All nine combinations, including the three the WO calls out as the point of the whole change: an armed autopilot that does not hold the seat. |
| `test_the_arm_reading_is_unmoved_by_every_seat_state` | Independence, direction one: hold the daemon's report fixed, walk every seat state, and assert the arm text never changes. |
| `test_the_seat_reading_is_unmoved_by_every_arm_state` | Independence, direction two -- the mirror, which matters just as much: arming must never appear to change who holds the keyboard. |
| `test_arm_reads_a_different_input_than_the_seat_badge_entirely` | Arm reads a different input than the seat badge entirely. |
| `test_lock_state_words_never_appear_in_any_arm_label` | ARM != take the human lock, pinned at the vocabulary level. |
| `test_no_key_and_no_seat_transition_can_make_the_indicator_read_armed` | Accept #3, behaviourally. |
| `test_that_assertion_is_not_vacuous_only_the_daemons_report_can_arm` | The companion without which the test above proves nothing. |
| `test_the_chip_only_ever_sees_the_object_the_status_provider_returned` | The chip only ever sees the object the status provider returned. |
| `test_the_cockpit_holds_no_arm_state_of_its_own` | There is nothing to flip. |
| `test_a_dropped_status_poll_degrades_to_unknown_never_to_a_calm_disarmed` | The failure mode with real consequences: the daemon goes away mid-session. |
| `test_a_raising_status_provider_shows_unknown_rather_than_a_calm_claim` | A raising status provider shows unknown rather than a calm claim. |
| `test_the_arm_chip_lands_immediately_right_of_the_seat_chip` | The arm chip lands immediately right of the seat chip. |
| `test_the_liveness_cluster_still_survives_beside_both_chips` | The liveness cluster still survives beside both chips. |
| `test_the_armed_chip_carries_the_badge_attributes` | The armed chip carries the badge attributes. |
| `test_the_disarmed_chip_stays_calm_and_unbadged` | The disarmed chip stays calm and unbadged. |
| `test_a_raising_arm_composer_never_crashes_the_draw_pass` | A raising arm composer never crashes the draw pass. |
| `test_omitting_the_arm_chip_is_byte_identical_to_the_pre_wo_row` | Backward compatibility, structurally: with no arm chip supplied the composer must produce exactly the row it produced before this WO. |
| `test_the_row_is_still_exactly_width_characters_with_the_arm_chip_present` | The invariant every caller of this row depends on. |
| `test_line_and_segments_stay_byte_identical_with_an_arm_chip` | Line and segments stay byte identical with an arm chip. |
| `test_the_arm_chip_is_all_or_nothing_never_truncated` | The width-pressure safety property. |
| `test_the_seat_chip_outranks_the_arm_chip_under_width_pressure` | The seat chip outranks the arm chip under width pressure. |
| `test_the_arm_chip_renders_even_when_the_seat_makes_no_claim` | The arm chip renders even when the seat makes no claim. |
| `test_a_malformed_arm_chip_degrades_to_no_chip_and_never_raises` | House hardening discipline: every public composer here is never-raises regardless of input shape. |
| `test_an_unknown_arm_tone_degrades_to_plain_rather_than_dropping_the_chip` | A tone outside the draw layer's vocabulary must not cost the operator the chip itself -- the text is the load-bearing part, the tone is emphasis. |
| `test_exactly_one_status_poll_per_draw_with_the_arm_chip_wired` | The arm chip is a new consumer of the shared per-draw snapshot; it must not become a second poll. |
| `test_control_seat_still_never_reads_the_daemon_status_itself` | Control seat still never reads the daemon status itself. |
