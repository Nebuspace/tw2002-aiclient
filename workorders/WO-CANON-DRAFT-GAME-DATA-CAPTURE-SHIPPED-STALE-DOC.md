# WO-CANON-DRAFT-GAME-DATA-CAPTURE-SHIPPED-STALE-DOC

## Goal
Flip `canon/engine/game-data-store.md` Gaps that claimed capture→persist "not yet built" —
`GameDataCapture` is wired on tip.

## Scope
- `canon/engine/game-data-store.md`
- this WO file

## Accept
1. Gaps no longer claim the live capture-and-persist trigger is missing.
2. Opportunistic `game_data_capture` + `app.py` idle tick called out as LIVE.
3. `tw probe` remains correctly scoped (banner classify only).
4. Introspector provisional-by-construction honesty preserved.
5. Citations list `game_data_capture.py`.

## Proof
- `git grep -n 'not yet wired\|not yet built\|missing link' -- canon/engine/game-data-store.md` → empty for capture-loop claims
- offline suite; live-prove n/a (docs)

## Out of scope
PWO-092 Option B navigating introspection · broader live StarDock corpus refinement
