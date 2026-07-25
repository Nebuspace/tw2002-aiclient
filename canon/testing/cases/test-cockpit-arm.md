---
type: Reference
title: Test Cases — test_cockpit_arm
description: Cockpit arm.
resource: repo://tw2002-aiclient/tests/test_cockpit_arm.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_arm.py`

_Cockpit arm._

| Test | Blurb |
|------|-------|
| `test_literal_true_is_the_only_thing_that_reads_as_armed` | Literal true is the only thing that reads as armed. |
| `test_literal_false_is_the_only_thing_that_reads_as_disarmed` | Literal false is the only thing that reads as disarmed. |
| `test_a_truthy_non_bool_is_unknown_not_armed_and_not_disarmed` | The load-bearing asymmetry, stated once here and relied on everywhere else. |
| `test_a_falsy_non_bool_is_unknown_too_and_never_a_calm_disarmed_claim` | The mirror of the case above, and the more counter-intuitive one: a cleanly-FALSY non-bool is still not proof of disarm. |
| `test_every_unusable_payload_shape_is_unknown` | Every unusable payload shape is unknown. |
| `test_a_hostile_mapping_whose_get_raises_is_unknown_not_a_crash` | A hostile mapping whose get raises is unknown not a crash. |
| `test_a_hostile_inner_block_whose_get_raises_is_unknown_not_a_crash` | A hostile inner block whose get raises is unknown not a crash. |
| `test_the_daemons_real_hardcoded_status_shape_reads_as_disarmed` | The daemons real hardcoded status shape reads as disarmed. |
| `test_each_state_has_its_own_distinct_label` | Each state has its own distinct label. |
| `test_the_unknown_label_uses_canons_own_unknown_glyph` | The unknown label uses canons own unknown glyph. |
| `test_a_truncated_label_can_never_impersonate_a_different_label` | A truncated label can never impersonate a different label. |
| `test_every_label_is_plain_ascii_so_no_glyph_twin_is_needed` | Every label is plain ascii so no glyph twin is needed. |
| `test_armed_wears_the_attention_tone` | Armed wears the attention tone. |
| `test_unknown_wears_the_attention_tone_too` | Unknown wears the attention tone too. |
| `test_only_a_proven_disarm_gets_the_calm_muted_tone` | Only a proven disarm gets the calm muted tone. |
| `test_the_tone_vocabulary_is_exactly_what_the_draw_layer_already_resolves` | The tone vocabulary is exactly what the draw layer already resolves. |
| `test_arm_never_claims_the_ok_tone_reserved_for_the_app_chip` | Arm never claims the ok tone reserved for the app chip. |
| `test_compose_returns_the_matching_label_and_tone_pair` | Compose returns the matching label and tone pair. |
| `test_compose_always_yields_a_non_empty_label` | The chip never blanks. |
| `test_compose_takes_exactly_one_argument_the_daemon_report` | A structural half of Accept #3, cheap and exact: the chip's only input is the status payload. |
| `test_no_public_entry_point_raises_on_any_input_shape` | No public entry point raises on any input shape. |
| `test_an_exploding_running_value_is_unknown_not_armed` | An exploding running value is unknown not armed. |
