# WO-PWO-092-GAME-DATA-KERNEL — Layer-B game_data store (Option A)

> Status: **DONE** · origin `73e7428` (#345) · seat `impl-aiclient-cursor` · Accept 2026-08-03  
> Type: product substrate · PWO-092  
> Tip base: `f5e3b18` → merged `73e7428`

## Goal
Ship the two-layer game-data **kernel**: schema + `introspected` source gate (write+load) + world-keyed persist, proven against `tests/fixtures/mock_game_data.json`.

## Scope
- A: `tw2002_aiclient/game_data.py` (new)
- B: `tests/test_game_data.py`
- C: ULTRACODE + P7 PREP tip → **LIVE** (kernel; introspector still deferred)
- D: this WO file

## Constraints
No `introspector.py`. No live TWGS. No PWO-100 port-economics floors. No archive BANK test revival. No send paths.

## Accept
1. Fixture loads with source gate green
2. Non-`introspected` source refused on validate / load / persist (nothing written)
3. `persist_ship_row` → `load_world_game_data` round-trip under `tmp_path`

## Proof
`pytest tests/test_game_data.py` green · CI suite.
