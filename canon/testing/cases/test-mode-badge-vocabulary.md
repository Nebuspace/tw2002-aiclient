---
type: Reference
title: Test Cases — Mode Badge Vocabulary
description: WO-P5-060 lane C -- structural proof that no retired mode-badge.
resource: repo://tw2002-aiclient/tests/test_mode_badge_vocabulary.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_mode_badge_vocabulary.py`

_WO-P5-060 lane C -- structural proof that no retired mode-badge_

| Test | Blurb |
|------|-------|
| `test_product_tree_has_no_retired_mode_badge_vocabulary` | Product tree has no retired mode badge vocabulary. |
| `test_scanner_detects_a_synthetic_ai_pilot_badge_string` | Scanner detects a synthetic ai pilot badge string. |
| `test_scanner_detects_a_synthetic_auto_loop_badge_string` | Scanner detects a synthetic auto loop badge string. |
| `test_scanner_excludes_module_class_and_function_docstrings_citing_the_ban` | A docstring is exactly where this project's own ``D5: no. |
| `test_scanner_still_fires_on_a_second_bare_string_statement_that_is_not_a_docstring` | Soundness edge case: only the FIRST statement of a scope's body is. |
| `test_scanner_detects_banned_fragment_inside_an_fstring` | f-string literal fragments surface as ordinary ``ast. |
| `test_scanner_detects_lowercase_ai_pilot_as_a_dict_key_and_as_a_kwarg_value` | Scanner detects lowercase ai pilot as a dict key and as a kwarg value. |
| `test_scanner_is_case_sensitive_and_does_not_false_positive_on_unrelated_text` | The banned terms are matched by a plain, case-sensitive substring. |
| `test_scan_product_tree_finds_python_files` | Belt-and-suspenders on the gate's own setup: the tree walk must. |
