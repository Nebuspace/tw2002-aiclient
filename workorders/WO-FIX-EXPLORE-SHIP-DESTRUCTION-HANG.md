# WO-FIX-EXPLORE-SHIP-DESTRUCTION-HANG

**Found during:** orchestrator live-drive credit-doubling proof, 2026-08-07, `scout_rogue`
profile / `gone_rogue` server (sacrificial, `crawl_sacrificial=true`).

## What happened

Fresh 100,000-credit character, `explore start --world-id gone_rogue --turn-budget 300
--dock-new-ports --min-sectors 0`. Explore correctly discovered 25 sectors / issued 64
sends, then autopilot-warped into an uncharted sector with 160 hostile fighters:

```
Fighters: 160 (The Red Dragon) [Offensive]
Fighter Attack!
Combat computer reports damages of 6 battle points!
Life Support knocked out!  Energy generation shut down!
Your *** Scorched *** has been destroyed!
You will have to start over from scratch!
Maybe you'll have better luck with a different ship!
```

This drops the connection back to the **outer BBS door menu** (`T`/`I`/`S`/`H`/`M`/`X` —
the screen normally seen once, immediately after telnet connect, before ever entering the
game). The explore loop did not recognize either the destruction message or this outer-menu
state as a halt condition and **did not act at all** — no send, no halt, no error. `tw
explore status` kept reporting the same `distinct_sectors: 25, sends_issued: 64` for over 5
minutes while the daemon process sat at high CPU. The server's own inactivity timer
eventually fired (60s → 30s → 10s warnings) and force-disconnected the session, landing on
a completely different screen (`gone_rogue`'s outer game-select list) with the daemon still
reporting `running: true` throughout — a silent zombie state, not a clean halt.

## Why this matters

`sector_explore.py`'s own documented design principle (line ~825-831): *"Every unexpected
screen halts the whole run rather than backing out... a halt leaves the human on a real
screen."* That principle is correct and already implemented for other unrecognized-screen
cases (`dock_report_unreadable`, `HALT_NOT_DRIVABLE`, etc. — see `halt_reasons.py`). Ship
destruction mid-explore is a plainly foreseeable outcome of autopilot warping through
uncharted, potentially hostile sectors, yet it has **zero** classification anywhere in the
codebase (`grep -rn "destroyed\|Scorched\|start over from scratch"` across
`tw2002_aiclient/` and `canon/` returns nothing relevant). It falls through every existing
matcher, so the loop neither halts cleanly nor takes any recovery action — it just sits,
silently burning the server's patience until the connection is killed out from under it.

## Fix

1. Add a `ship_destroyed` (or similarly-named) classification in `classify.py` matching the
   "*** has been destroyed!*** / You will have to start over from scratch!" text pattern
   (verify exact server-dialect wording tolerance — other TWGS servers may phrase this
   slightly differently; check `canon/research/tw2002-screen-patterns.md` first for any
   already-documented variant before hand-rolling a new regex).
2. Wire it into `sector_explore.py`'s halt path with a new named halt reason (e.g.
   `halt_ship_destroyed`) — mirroring the existing `HALT_NOT_DRIVABLE` /
   `dock_report_unreadable` pattern, so it surfaces the same way other unexpected-screen
   halts do: loud, named, leaving the human (or the next `tw ensure` call) on a real,
   recognized screen rather than a zombie idle.
3. Confirm the resulting outer-BBS-menu screen (`T`/`I`/`S`/`H`/`M`/`X`) is itself a
   recognized classification too — even after the halt fires, a subsequent `tw ensure`
   needs to be able to navigate back in from this exact screen (character now needs to
   restart from scratch, which may itself route through `char_create`/registration again —
   confirm and document what `tw ensure` should do post-destruction: fresh-register, or
   halt and let the operator decide).
4. Do **not** attempt to make explore avoid combat / dodge hostile sectors — that's a
   different, much larger scope (routing/danger-avoidance policy) and explicitly out of
   scope here. This WO is only about recognizing the outcome and halting cleanly instead of
   hanging silently.

## Accept

1. A sacrificial live re-run that encounters ship destruction mid-explore halts within one
   settle cycle (not multiple minutes / not requiring the server's own inactivity timeout)
   with a named halt reason surfaced in `tw explore status`.
2. `tw status` / daemon state accurately reflects "halted, not running" immediately after —
   no zombie `running: true` while idle.
3. Unit test pinning the classification against the exact captured transcript text above
   (`logs/session-20260807T204741Z.log` on the machine this was found, if still present —
   otherwise the literal string block quoted above).
4. Documented (in this WO's own follow-up note or `canon/research/tw2002-screen-patterns.md`)
   what `tw ensure` does when invoked against a post-destruction outer-menu screen.

## Proof

Offline: unit test on the classifier + halt-path wiring. Live: sacrificial re-run
(`crawl_sacrificial=true` profile) deliberately or incidentally encountering hostile-sector
destruction, confirming a clean named halt rather than a stall.

## Owner

tw2002-aiclient — `tw2002_aiclient/session/classify.py`, `tw2002_aiclient/session/sector_explore.py`,
`tw2002_aiclient/halt_reasons.py`.

## Refs

Live transcript: `logs/session-20260807T204741Z.log` (RX at 2026-08-07T20:48:48Z — ship
destruction; RX at 20:52:48Z–20:53:48Z — inactivity warnings; 20:53:49Z — forced
disconnect). Explore run: `world_id=gone_rogue`, profile `scout_rogue`, started
2026-08-07T20:48:04Z. Existing halt-design precedent: `sector_explore.py:825-831`,
`halt_reasons.py`.


## Follow-up note — `tw ensure` after destruction (Accept #4)

After a clean `halt_ship_destroyed`, the wire typically shows the outer BBS
door (`T`/`I`/`S`/`H`/`M`/`X`, prompt `Enter your choice:`). Today that
shape classifies as `menu` (content anchor), not `game_select`. Operator
path: stop explore (already halted) → `tw ensure` / re-login as for a fresh
session. Character is gone; do **not** expect ensure to resurrect the ship —
fresh registration / char_create is required. A dedicated `bbs_door` class
is optional polish, not required for this halt WO.
