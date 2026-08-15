# WO-AICLIENT-WIRE-FIGHTER-PRICE-OBSERVE-FROM-SCREEN

**Goal:** Feed settle-edge watch-event screen text into
`play.fighter_price_scalars.observe_screen` on the play-loop idle tick so an
on-screen Class-0 unit-price quote can populate status / GOALS without a
manual inject.

**Scope:**
- `tw2002_aiclient/fighter_price_capture.py` (new)
- `tw2002_aiclient/app.py` (idle-tick wire)
- `tests/test_fighter_price_capture.py`

**Out of scope:** inventing tip `FIGHTER_UNIT_PRICE_CLASS0`; buy EXECUTE;
live StarDock menu crawl (stays GATED
`WO-BUILD-FIGHTER-CLASS0-LIVE-PRICE-CAPTURE`).

**Accept:**
- Idle tick constructs `FighterPriceCapture` and calls `.tick(play, profile)`.
- Matching screen text → `observe` → `merge` can expose `fighter_unit_price`
  / `fighter_price_class0`.
- Fail-closed on empty / non-matching / missing scalars; never raises on tick.
- Dedupes unchanged screen fingerprints.

**Proof:**
- `.venv/bin/python -m pytest tests/test_fighter_price_capture.py tests/test_fighter_price_status.py -q`
- `live-prove: n/a` — offline observe wire only; no live-drive / login path.
