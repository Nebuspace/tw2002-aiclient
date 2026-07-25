---
type: Reference
title: Test Cases — test_mode_badge_vocabulary
description: Mode badge vocabulary.
resource: repo://tw2002-aiclient/tests/test_mode_badge_vocabulary.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_mode_badge_vocabulary.py`

_Mode badge vocabulary._

| Test | Blurb |
|------|-------|
| `test_product_tree_has_no_retired_mode_badge_vocabulary` | Product tree has no retired mode badge vocabulary. |
| `test_scanner_detects_a_synthetic_ai_pilot_badge_string` | Scanner detects a synthetic ai pilot badge string. |
| `test_scanner_detects_a_synthetic_auto_loop_badge_string` | Scanner detects a synthetic auto loop badge string. |
| `test_scanner_excludes_module_class_and_function_docstrings_citing_the_ban` | Scanner excludes module class and function docstrings citing the ban. |
| `test_scanner_still_fires_on_a_second_bare_string_statement_that_is_not_a_docstring` | Soundness edge case: only the FIRST statement of a scope's body is ever a syntactic docstring. |
| `test_scanner_detects_banned_fragment_inside_an_fstring` | Scanner detects banned fragment inside an fstring. |
| `test_scanner_detects_lowercase_ai_pilot_as_a_dict_key_and_as_a_kwarg_value` | Scanner detects lowercase ai pilot as a dict key and as a kwarg value. |
| `test_scanner_is_case_sensitive_and_does_not_false_positive_on_unrelated_text` | The banned terms are matched by a plain, case-sensitive substring check -- a differently-cased rendering (e.g. |
| `test_scan_product_tree_finds_python_files` | Scan product tree finds python files. |
