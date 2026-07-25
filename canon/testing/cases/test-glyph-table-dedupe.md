---
type: Reference
title: Test Cases — Glyph Table Dedupe
description: Proof lane for ``WO-AUDIT-GLYPH-TABLE-DEDUPE``: ``screens.
resource: repo://tw2002-aiclient/tests/test_glyph_table_dedupe.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_glyph_table_dedupe.py`

_Proof lane for ``WO-AUDIT-GLYPH-TABLE-DEDUPE``: ``screens.py``'s launcher_

| Test | Blurb |
|------|-------|
| `test_shared_box_keys_are_byte_identical_to_draw_unicode` | Shared box keys are byte identical to draw unicode. |
| `test_shared_box_keys_are_byte_identical_to_draw_ascii` | Shared box keys are byte identical to draw ascii. |
| `test_sel_key_literals_unchanged` | Sel key literals unchanged. |
| `test_unicode_table_key_set_is_draw_keys_plus_sel` | Unicode table key set is draw keys plus sel. |
| `test_ascii_table_key_set_is_draw_keys_plus_sel` | Ascii table key set is draw keys plus sel. |
| `test_glyph_set_selects_unicode_table_by_default` | Glyph set selects unicode table by default. |
| `test_glyph_set_selects_ascii_table_under_tw2002_ascii` | Glyph set selects ascii table under tw2002 ascii. |
| `test_existing_suite_sweep_unchanged` | Existing suite sweep unchanged. |
