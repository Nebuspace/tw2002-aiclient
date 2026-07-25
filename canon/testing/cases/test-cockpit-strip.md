---
type: Reference
title: Test Cases — Cockpit Strip
description: Pure profile/character-strip composer tests (PWO-032, Layer-A).
resource: repo://tw2002-aiclient/tests/test_cockpit_strip.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_strip.py`

_Pure profile/character-strip composer tests (PWO-032, Layer-A)._

| Test | Blurb |
|------|-------|
| `test_healthy_profile_composes_exact_string` | Healthy profile composes exact string. |
| `test_healthy_profile_ascii_mode_is_identical_to_unicode_mode` | Healthy profile ascii mode is identical to unicode mode. |
| `test_missing_host_falls_back_to_question_mark` | Missing host falls back to question mark. |
| `test_blank_host_falls_back_to_question_mark` | Blank host falls back to question mark. |
| `test_missing_game_letter_falls_back_to_em_dash` | Missing game letter falls back to em dash. |
| `test_missing_game_letter_ascii_mode_is_identical_no_fabricated_hyphen` | Missing game letter ascii mode is identical no fabricated hyphen. |
| `test_missing_handle_falls_back_to_question_mark` | Missing handle falls back to question mark. |
| `test_all_fields_missing_no_crash_all_fallbacks` | All fields missing no crash all fallbacks. |
| `test_all_fields_missing_ascii_mode_no_crash_no_fabricated_glyphs` | All fields missing ascii mode no crash no fabricated glyphs. |
| `test_empty_strings_treated_same_as_none` | Empty strings treated same as none. |
| `test_non_str_host_coerces_instead_of_raising` | Non str host coerces instead of raising. |
| `test_non_str_handle_float_coerces_instead_of_raising` | Non str handle float coerces instead of raising. |
| `test_non_str_game_letter_coerces_and_still_truncates_to_one_char` | Non str game letter coerces and still truncates to one char. |
| `test_all_fields_non_str_no_crash` | All fields non str no crash. |
| `test_multi_char_game_letter_truncates_to_first_char` | Multi char game letter truncates to first char. |
| `test_multi_char_game_letter_ascii_mode_still_truncates` | Multi char game letter ascii mode still truncates. |
| `test_embedded_newline_collapses_to_single_space` | Embedded newline collapses to single space. |
| `test_embedded_tab_collapses_to_single_space` | Embedded tab collapses to single space. |
| `test_embedded_control_char_stripped_no_raw_control_bytes` | Embedded control char stripped no raw control bytes. |
| `test_embedded_c1_control_stripped_no_escape_injection` | Embedded c1 control stripped no escape injection. |
| `test_multiple_embedded_newlines_collapse_to_one_space_each` | Multiple embedded newlines collapse to one space each. |
| `test_width_invariant_never_exceeded` | Width invariant never exceeded. |
| `test_zero_width_returns_empty_string` | Zero width returns empty string. |
| `test_negative_width_returns_empty_string` | Negative width returns empty string. |
| `test_minimal_width_truncates_at_tail_never_raises` | Minimal width truncates at tail never raises. |
| `test_broken_profile_at_minimal_width_no_exception` | Broken profile at minimal width no exception. |
| `test_from_row_uses_host_over_server` | From row uses host over server. |
| `test_from_row_falls_back_to_server_when_host_missing` | From row falls back to server when host missing. |
| `test_from_row_missing_attributes_no_crash` | From row missing attributes no crash. |
| `test_from_row_ascii_mode_propagates` | From row ascii mode propagates. |
