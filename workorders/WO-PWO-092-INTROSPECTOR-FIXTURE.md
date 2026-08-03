# WO-PWO-092-INTROSPECTOR-FIXTURE

**Status:** build (PWO-092 Option A)
**Hub GO:** 2026-08-03T15:20:00Z Propose A

## Goal
Ship fixture/offline `introspector.py` — pure screen-text → Layer-B game_data rows. Zero live crawl/send.

## Scope
- `tw2002_aiclient/introspector.py`
- `tw2002_aiclient/game_data.py` (`validate_cargo_hold_row` + docstring ceiling)
- `tests/test_introspector.py` (+ existing `tests/fixtures/stardock_*.txt`)
- tip stamps · DECISION · this WO

## Accept
- Parse shipyard / cargo-hold / equipment fixtures → introspected* sources.
- Round-trip through `load_game_data` / validators; non-introspected source refused.
- No production live crawl / send path.

## Proof
`pytest tests/test_introspector.py tests/test_game_data.py` · live-prove n/a.

## Out of scope
Option B live session introspect.
