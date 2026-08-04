# WO-AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP

**Status:** CLAIMED by `impl-aiclient-cursor` (standing self-scope · hub GO 2026-08-04T15:58:45Z)
**Priority:** HIGH
**Depends-on:** none (PWO-092 Option A introspector + game_data already LIVE)
**Gated:** no — opportunistic capture only; PWO-092 Option B live crawl/send remains HELD

## Goal

Wire a live **opportunistic** daemon-tick / observe hook: when a StarDock / shipyard / equipment listing screen is already classified and visible in the session buffer, call `introspector` parse then `game_data` persist — so Layer-B rows can fill from real play without a crawl/send.

## Scope

- Hook on existing classify/observe/tick path (no new send, no menu crawl, no sacrificial profile)
- `tw2002_aiclient/introspector.py` (callers only — parser stays pure)
- `tw2002_aiclient/game_data.py` (persist path as-is)
- New small module or function owning the capture trigger + tests
- `workorders/WO-AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP.md` (this file)

## Out of scope

- PWO-092 Option B live TWGS crawl / session introspect that *navigates* or *sends*
- FOCUS/overlay bridge, TW-22 auto-max-holds, ship-catalog consumers (downstream WOs)
- Authored numeric Layer-A values

## Accept

1. Product path (not only tests) invokes introspector → persist when a matching classified screen buffer is observed.
2. Zero send / crawl / connection side-effects from the capture path.
3. Source gate still refuses non-`introspected*` rows.
4. Pins: unit tests covering fire / no-fire (wrong screen) / persist round-trip; optional inject-defect check.
5. live-prove: `n/a` or DEFERRED→Cursor diversity only if a safe half exists; honest NOT-ATTEMPTED if turn-spending arm required.

## Proof

`pytest` targeted new + `tests/test_introspector.py` + `tests/test_game_data.py`; suite green on tip. STATUS with SHA + evidence.

## Refs

- `canon/engine/game-data-store.md` (missing live trigger ~215–221)
- `canon/DECISIONS.md` PWO-092 Option A LIVE / Option B HELD
- queue-aiclient.md row AUDIT-BUILD-GAMEDATA-CAPTURE-LOOP
