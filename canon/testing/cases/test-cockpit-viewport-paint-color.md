---
type: Reference
title: Test Cases — Cockpit Viewport Paint Color
description: Wire-level tests: ``PlayShellScreen.
resource: repo://tw2002-aiclient/tests/test_cockpit_viewport_paint_color.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_viewport_paint_color.py`

_Wire-level tests: ``PlayShellScreen.draw()`` actually PAINTS TWGS color_

| Test | Blurb |
|------|-------|
| `test_known_palette_lands_at_the_right_cells_with_the_right_attr` | Known palette lands at the right cells with the right attr. |
| `test_color_screen_count_mismatch_drops_color_but_still_paints_text` | Color screen count mismatch drops color but still paints text. |
| `test_pair_exhaustion_degrades_to_uncolored_text_without_crash` | Pair exhaustion degrades to uncolored text without crash. |
| `test_chrome_colors_survive_repeated_game_cell_allocation_across_draws` | Chrome colors survive repeated game cell allocation across draws. |
| `test_hostile_escape_payload_neutralized_even_under_a_color_run` | Hostile escape payload neutralized even under a color run. |
