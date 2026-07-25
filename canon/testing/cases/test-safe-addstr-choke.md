---
type: Reference
title: Test Cases — test_safe_addstr_choke
description: Safe addstr choke.
resource: repo://tw2002-aiclient/tests/test_safe_addstr_choke.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_safe_addstr_choke.py`

_Safe addstr choke._

| Test | Blurb |
|------|-------|
| `test_c0_and_c1_controls_neutralize_to_space_per_sanitize_controls_mapping` | C0 and c1 controls neutralize to space per sanitize controls mapping. |
| `test_injected_escape_sequence_marker_present_absent_pair` | Injected escape sequence marker present absent pair. |
| `test_wide_char_straddling_width_boundary_drops_whole_not_split` | Wide char straddling width boundary drops whole not split. |
| `test_narrow_ascii_is_unaffected_by_cell_width_accounting` | Narrow ascii is unaffected by cell width accounting. |
| `test_old_safe_addstr_stopped_one_column_short_of_window_edge` | RED baseline: prove the pre-fix limitation actually existed. |
| `test_new_safe_addstr_reaches_the_window_true_last_column` | New safe addstr reaches the window true last column. |
| `test_safe_addstr_delegates_every_call_onto_cockpit_draw_safe_write` | Safe addstr delegates every call onto cockpit draw safe write. |
| `test_safe_addstr_propagates_choke_exceptions_uncaught` | Safe addstr propagates choke exceptions uncaught. |
