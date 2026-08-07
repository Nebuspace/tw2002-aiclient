# WO-CLEANUP-WIRE-EQUIPMENT-LISTING-CAPTURE

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** MED (Cycle dead-symbols batch · parse_*_listing orphans)  
**Depends-on:** none

## Goal

Wire `parse_scanner_listing` / `parse_transwarp_listing` / `parse_item_listing`
into the opportunistic game-data capture path (same observe-only pattern as
shipyard + cargo-hold), so the built+tested parsers have a product caller.

## Scope

- `tw2002_aiclient/game_data.py` — validate + persist for scanner/transwarp/item
- `tw2002_aiclient/game_data_capture.py` — parse + persist on idle tick / `capture_screen`
- `tests/test_game_data_capture.py` — equipment fixture pins
- this WO file

## Accept

1. Sitting on `stardock_equipment_listing.txt`-shaped text via `GameDataCapture.tick`
   persists scanners ≥1, transwarp ≥1, items ≥1 with `source` starting `introspected`.
2. Shipyard + cargo-hold capture paths remain green.
3. No send/crawl symbols added to `game_data_capture`.

## Proof

```bash
.venv/bin/python -m pytest tests/test_game_data_capture.py tests/test_introspector.py -q -n0
```

Live-prove: **n/a** (offline fixture capture; no session/login arm).
