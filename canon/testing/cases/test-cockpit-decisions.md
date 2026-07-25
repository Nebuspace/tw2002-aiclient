---
type: Reference
title: Test Cases — Cockpit Decisions
description: Pure DECISIONS-panel composer tests (PWO-036, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_decisions.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_decisions.py`

_Pure DECISIONS-panel composer tests (PWO-036, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_status_none_is_honest_empty` | Status none is honest empty. |
| `test_status_empty_dict_is_honest_empty` | Status empty dict is honest empty. |
| `test_autopilot_trace_key_absent_is_honest_empty` | Autopilot trace key absent is honest empty. |
| `test_autopilot_trace_non_dict_is_honest_empty` | Autopilot trace non dict is honest empty. |
| `test_candidates_absent_is_honest_empty` | Candidates absent is honest empty. |
| `test_candidates_empty_list_is_honest_empty` | Candidates empty list is honest empty. |
| `test_candidates_non_list_is_honest_empty` | Candidates non list is honest empty. |
| `test_candidates_all_non_dict_entries_dropped_is_honest_empty` | Candidates all non dict entries dropped is honest empty. |
| `test_status_non_dict_types_never_raise` | Status non dict types never raise. |
| `test_full_fixture_exact_lines_with_glyph_placement` | Full fixture exact lines with glyph placement. |
| `test_order_is_never_resorted_by_this_module` | Order is never resorted by this module. |
| `test_gated_wins_over_chosen_precedence` | Gated wins over chosen precedence. |
| `test_chosen_none_renders_all_non_gated_as_other` | Chosen none renders all non gated as other. |
| `test_chosen_not_matching_any_candidate_marks_none_as_chosen` | Chosen not matching any candidate marks none as chosen. |
| `test_non_str_chosen_never_raises_and_does_not_blank_the_panel` | Non str chosen never raises and does not blank the panel. |
| `test_gated_candidate_uses_blocked_glyph_and_reason` | Gated candidate uses blocked glyph and reason. |
| `test_gated_candidate_missing_reason_falls_back_to_unknown_detail` | Gated candidate missing reason falls back to unknown detail. |
| `test_ungated_missing_ev_and_rationale_show_honest_unknown` | Ungated missing ev and rationale show honest unknown. |
| `test_missing_gated_key_defaults_to_ungated` | Missing gated key defaults to ungated. |
| `test_unrecognized_kind_is_humanized_not_dropped` | Unrecognized kind is humanized not dropped. |
| `test_missing_kind_degrades_to_unknown_detail_label` | Missing kind degrades to unknown detail label. |
| `test_negative_ev_renders_signed` | Negative ev renders signed. |
| `test_non_dict_candidate_entries_are_dropped_not_fabricated` | Non dict candidate entries are dropped not fabricated. |
| `test_non_finite_ev_never_raises_and_degrades_to_unknown` | Non finite ev never raises and degrades to unknown. |
| `test_non_numeric_ev_never_raises` | Non numeric ev never raises. |
| `test_raising_str_on_kind_and_gate_reason_never_raises` | Raising str on kind and gate reason never raises. |
| `test_raising_bool_on_gated_never_raises` | Raising bool on gated never raises. |
| `test_raising_float_on_ev_never_raises` | Raising float on ev never raises. |
| `test_control_chars_in_gate_reason_pass_through_safely` | Control chars in gate reason pass through safely. |
| `test_dict_subclass_with_hostile_get_is_dropped` | Dict subclass with hostile get is dropped. |
| `test_width_non_int_never_raises` | Width non int never raises. |
| `test_width_clip_sweep_every_line_within_budget` | Width clip sweep every line within budget. |
| `test_width_zero_or_negative_empties_every_line` | Width zero or negative empties every line. |
| `test_width_zero_on_empty_state_is_two_empty_lines` | Width zero on empty state is two empty lines. |
| `test_no_composed_line_begins_with_a_bare_word` | No composed line begins with a bare word. |
| `test_fixed_vocabulary_never_uses_an_imperative_leading_word` | Fixed vocabulary never uses an imperative leading word. |
