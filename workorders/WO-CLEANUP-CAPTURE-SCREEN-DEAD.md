# WO-CLEANUP-CAPTURE-SCREEN-DEAD

**Goal:** Wire or delete unused `capture_screen()` in `game_data_capture.py`.

**Scope:**
- `tw2002_aiclient/game_data_capture.py`
- `tests/test_game_data_capture.py`
- this WO file

**Depends-on:** none

**Accept:**
- `capture_screen` has a real call site on the product path (`GameDataCapture._tick`), **or** the symbol is deleted.
- Existing tick persist / dedupe pins still green.
- No send / crawl API introduced.

**Proof:**
- `pytest tests/test_game_data_capture.py -n0`
- live-prove: `n/a` (offline observe-path cleanup; no session/login surface)

**Refs:** queue-aiclient unused-code / 6-lens aiclient audit 2026-08-04T23:38Z
