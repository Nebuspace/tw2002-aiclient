---
type: Reference
title: Test Cases — Cockpit Viewport
description: PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake.
resource: repo://tw2002-aiclient/tests/test_cockpit_viewport.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_cockpit_viewport.py`

_PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake_

| Test | Blurb |
|------|-------|
| `test_no_addstr_call_writes_into_the_game_interior_cells` | Bordered full tier: only the double-line border + 'GAME' title write. |
| `test_placeholder_string_never_reaches_any_addstr_call` | The retired placeholder text must not reach ANY addstr call in a. |
