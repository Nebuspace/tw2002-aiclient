---
type: Reference
title: Test Cases — Cockpit Fold
description: Pure responsive-fold composer tests (WO-P3-039, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_fold.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_fold.py`

_Pure responsive-fold composer tests (WO-P3-039, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_status_none_collapses_to_pane_empty` | Status none collapses to pane empty. |
| `test_status_empty_dict_collapses_to_pane_empty` | Status empty dict collapses to pane empty. |
| `test_status_non_dict_types_never_raise_and_collapse` | Status non dict types never raise and collapse. |
| `test_all_three_sections_present_but_malformed_still_collapses` | All three sections present but malformed still collapses. |
| `test_full_fixture_section_order_labels_and_glyphs` | Full fixture section order labels and glyphs. |
| `test_section_labels_are_bare_uppercase_no_glyph_no_colon` | Section labels are bare uppercase no glyph no colon. |
| `test_no_ai_pilot_text_anywhere` | No ai pilot text anywhere. |
| `test_trace_only_others_honest_empty_still_render` | Trace only others honest empty still render. |
| `test_goals_only_others_honest_empty_still_render` | Goals only others honest empty still render. |
| `test_focus_only_others_honest_empty_still_render` | Focus only others honest empty still render. |
| `test_hostile_autopilot_trace_payload_drops_trace_section_others_survive` | Hostile autopilot trace payload drops trace section others survive. |
| `test_hostile_focus_payload_drops_focus_section_others_survive` | Hostile focus payload drops focus section others survive. |
| `test_hostile_top_level_status_drops_all_sections_falls_back_to_pane_empty` | Hostile top level status drops all sections falls back to pane empty. |
| `test_width_clip_sweep_every_line_within_budget` | Width clip sweep every line within budget. |
| `test_width_zero_or_negative_empties_every_line_keeping_shape` | Width zero or negative empties every line keeping shape. |
| `test_hostile_width_never_raises` | Hostile width never raises. |
| `test_width_zero_goals_only_status_collapses_due_to_fixed_line_count_quirk` | Documented quirk (module docstring): GOALS always returns exactly 9. |
| `test_reuses_child_composers_verbatim_not_a_reimplementation` | Reuses child composers verbatim not a reimplementation. |
