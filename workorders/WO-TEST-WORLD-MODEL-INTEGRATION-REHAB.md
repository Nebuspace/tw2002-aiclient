# WO-TEST-WORLD-MODEL-INTEGRATION-REHAB — rehab or DELETE ignored world_model integration suite

**Status:** DONE · Cursor · PR #173 · **DELETE** · awaiting hub Accept  
**Posted:** 2026-07-28T16:01Z · hub (#149 AUDIT BANK-REHAB MED · BANK-DELETE queue drained)

## Goal

Honest disposition for ignored `tests/test_world_model_integration.py` (twclient-era). Product `world_model` is live (#164/#165/#166). Either **rehab** onto in-tree APIs + un-ignore, or **DELETE** if the archive suite only covers deleted APIs and live pins already supersede (`test_world_model*.py` / landmarks / known_sector_count).

## Disposition (Cursor · evidence)

**DELETE** — not rehab.

| Evidence | Finding |
|---|---|
| Collect | `ModuleNotFoundError: twclient` at import (`from twclient import credentials, protocol, state_parser, world_model`) |
| Suite shape | ~22 cases drive archive `protocol.dispatch(..., "do", ...)` FakeSession → `_write_world_model` write-hook |
| Reborn write path | `session/sector_explore._ingest_settled_sector` → `world_model.write_from_state` — **no** `tw do` / bare-dispatch write-hook in product tree |
| Live pins that supersede | `tests/test_world_model.py` (write_from_state / bulk_upsert / isolation / concurrency) · `tests/test_world_model_landmarks.py` · `tests/test_sector_explore.py` (ingest) |

Rehab would reinvent a deleted protocol surface, not port a still-live contract. Same DELETE class as #151/#153/#155/#168–#172.

## Accept

1. Evidence-based rehab+un-ignore **or** DELETE+drop `--ignore=tests/test_world_model_integration.py`. ✅ DELETE
2. Do not invent stubs. Leave import-hygiene vacuity untouched. ✅
3. Suite green; live-prove `n/a`. Pause for LIVE-PROVE #169 if hub posts.

## Out of bounds

- CC #169 product paths · KEEP-IGNORED haggle/crawl/trade_driver rows

## Refs

- `AUDIT-TEST-IGNORE-LIST-LANDMINE.md` · live `world_model.py` · `session/sector_explore.py`
