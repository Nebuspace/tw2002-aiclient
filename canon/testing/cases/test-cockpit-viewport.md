---
type: Reference
title: Test Cases — test_cockpit_viewport
description: PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake window, no pty/curses init needed).
resource: repo://tw2002-aiclient/tests/test_cockpit_viewport.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cockpit_viewport.py`

_PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake window, no pty/curses init needed)._

| Test | Blurb |
|------|-------|
| `test_no_addstr_call_writes_into_the_game_interior_cells` | No addstr call writes into the game interior cells. |
| `test_placeholder_string_never_reaches_any_addstr_call` | Placeholder string never reaches any addstr call. |
