# WO-P2-G4-AUTOLOOP

**Status:** OPEN · Claude Code preferred (App drive / control_lock)  
**Posted:** 2026-07-26T00:55:00Z  
**Depends:** G3 `tw loops` on help (landed `1c084e5` / `385b176`)

## Goal

Ship `tw autoloop` (+ `loop_player` substrate as needed): App drives a taught loop under control_lock, stops on unknown / escalate, never invents loops.

## Scope

- `tw2002_aiclient/` loop player / autoloop CLI wire
- `tests/` proving empty / one-shot / stop-on-unknown
- Allowlist + README honesty when verb lands on `./tw --help`

## Constraints

- Max GO G2→G3→G4 already given (`@ 13:15:00Z`); still **no** crawl_sacrificial live enable
- Stop-on-unknown inviolable; AI never live-drives
- Hands off Max live attach if a play HEADS-UP is active
- Announce before shared `cli.py` collisions with Cursor

## Accept

1. `tw autoloop` listed on help only when real
2. Plays a taught loop; refuses / honest error when none / unreadable
3. Unrecognized screen → stop, no guessed keys
4. Suite green for targeted + related loops tests

## Proof

STATUS + SHA · targeted pytest · help surface before/after.

## Refs

`WO-P2-OPS-VERB-G-PREP.md` G4 · `WO-P2-G3-LOOPS.md` · north-star · control-and-escalation · M3 playable milestone
