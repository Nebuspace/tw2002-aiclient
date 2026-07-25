---
type: Reference
title: Test Cases — Safe Addstr Choke
description: Proof lane for ``WO-AUDIT-SAFE-ADDSTR-DEDUPE``: ``screens.
resource: repo://tw2002-aiclient/tests/test_safe_addstr_choke.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_safe_addstr_choke.py`

_Proof lane for ``WO-AUDIT-SAFE-ADDSTR-DEDUPE``: ``screens.py``'s launcher/_

| Test | Blurb |
|------|-------|
| `test_c0_and_c1_controls_neutralize_to_space_per_sanitize_controls_mapping` | Every C0 (\x00-\x1f) and C1 (\x7f-\x9f) control byte in text. |
| `test_injected_escape_sequence_marker_present_absent_pair` | The operator-typed ``edit_buf`` echo protection: an injected CSI. |
| `test_wide_char_straddling_width_boundary_drops_whole_not_split` | A CJK string whose wide (2-cell) characters straddle the available. |
| `test_narrow_ascii_is_unaffected_by_cell_width_accounting` | Sanity twin: plain ASCII is 1 cell per char, so the clip boundary is. |
| `test_old_safe_addstr_stopped_one_column_short_of_window_edge` | RED baseline: prove the pre-fix limitation actually existed. |
| `test_new_safe_addstr_reaches_the_window_true_last_column` | GREEN: the live delegate, same window/content, now reaches column. |
| `test_safe_addstr_delegates_every_call_onto_cockpit_draw_safe_write` | Monkeypatching ``cockpit_draw. |
| `test_safe_addstr_propagates_choke_exceptions_uncaught` | No local ``try/except`` remains in ``screens. |
