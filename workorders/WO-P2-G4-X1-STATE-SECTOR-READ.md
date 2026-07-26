# WO-P2-G4-X1-STATE-SECTOR-READ

**Status:** OPEN · Claude Code preferred · **blocked until** `protocol.py` free of C.2.1  
**Posted:** 2026-07-26 · M3 slice X1

## Goal

Current-sector (and related) read substrate: `state_parser.py` + `state` protocol verb so loop replay can re-check `start_anchor` against the **current** sector before any send (canon macros.md — not bypassable by force).

## Scope

- `tw2002_aiclient/session/state_parser.py` (new or port)
- `protocol.py` `state` verb (+ thin CLI if honesty requires)
- Pins: readable / unreadable / absent distinguishable; no keystroke

## Constraints

- Stop-on-unknown unchanged · no invent autoloop
- Sequence behind C.2.1 if same files
- Cite screen/archive patterns where relevant

## Accept

Sector (and documented fields) available via `state` without guessing; unreadable ≠ empty; suite green.

## Proof

STATUS + SHA · targeted pytest.

## Refs

CC G4 blocked-on-substrate 2026-07-26T03:17:33Z · macros.md start_anchor · M3 X1
