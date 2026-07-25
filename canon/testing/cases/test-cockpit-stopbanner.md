---
type: Reference
title: Test Cases — Cockpit Stopbanner
description: WO-P5-064 Layer-A -- the STOP banner composed from TYPED reason codes.
resource: repo://tw2002-aiclient/tests/test_cockpit_stopbanner.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_stopbanner.py`

_WO-P5-064 Layer-A -- the STOP banner composed from TYPED reason codes._

| Test | Blurb |
|------|-------|
| `test_every_canon_reason_code_renders_its_canon_label` | Every canon reason code renders its canon label. |
| `test_module_catalog_matches_canon_exactly_no_extra_no_missing` | The module's own map is the catalog, whole -- a code added to the. |
| `test_unknown_code_passes_through_as_its_own_text_never_invented_prose` | Unknown code passes through as its own text never invented prose. |
| `test_unknown_code_never_borrows_any_catalog_label` | The sharp edge of the same rule: not merely "some text appears",. |
| `test_empty_and_none_codes_render_the_canon_question_mark` | canon: "an empty code renders ``"? |
| `test_a_halt_with_no_reasons_at_all_still_states_the_halt_with_a_question_mark` | ``needs_attention`` set but an empty ``reasons`` list: there IS no. |
| `test_label_lookup_is_case_sensitive_and_does_not_fuzzy_match` | ``AUTOPILOT_HALTED`` is a DIFFERENT code from ``autopilot_halted``;. |
| `test_no_halt_renders_no_banner_at_all` | No halt renders no banner at all. |
| `test_needs_attention_true_is_the_only_thing_that_raises_the_banner` | Needs attention true is the only thing that raises the banner. |
| `test_bare_string_reasons_are_accepted_like_dict_reasons` | Bare string reasons are accepted like dict reasons. |
| `test_several_reasons_are_joined_not_collapsed_to_the_first` | Several reasons are joined not collapsed to the first. |
| `test_a_non_list_reasons_field_degrades_to_the_question_mark_not_iterated` | A non list reasons field degrades to the question mark not iterated. |
| `test_handoff_band_reads_human_when_the_wire_says_human_holds_the_keyboard` | Handoff band reads human when the wire says human holds the keyboard. |
| `test_handoff_band_never_claims_human_while_another_holder_is_reported` | Handoff band never claims human while another holder is reported. |
| `test_handoff_band_degrades_to_question_mark_when_the_holder_is_unknown` | Handoff band degrades to question mark when the holder is unknown. |
| `test_teach_band_offers_the_three_moves_as_labels` | Teach band offers the three moves as labels. |
| `test_each_teach_affordance_is_visible_at_the_halt` | Each teach affordance is visible at the halt. |
| `test_teach_band_is_labels_only_and_never_claims_a_move_is_running` | PWO-066+ owns the wires. |
| `test_full_height_is_three_bands_in_canon_order` | Full height is three bands in canon order. |
| `test_height_folds_from_the_bottom_reason_line_survives_last` | Height folds from the bottom reason line survives last. |
| `test_no_room_renders_nothing_rather_than_a_partial_glyph` | No room renders nothing rather than a partial glyph. |
| `test_every_line_fits_the_given_width` | Every line fits the given width. |
| `test_non_positive_width_keeps_the_line_count_and_empties_each_line` | Mirrors ``goals. |
| `test_a_narrow_banner_still_leads_with_the_attention_glyph` | A narrow banner still leads with the attention glyph. |
| `test_hostile_payloads_never_raise_and_never_blank_the_halt` | Hostile payloads never raise and never blank the halt. |
| `test_hostile_width_degrades_rather_than_raising` | Hostile width degrades rather than raising. |
| `test_hostile_height_degrades_rather_than_raising` | Hostile height degrades rather than raising. |
| `test_a_hostile_reason_entry_is_contained_and_its_siblings_still_render` | Per-item containment, the same shape ``goals. |
