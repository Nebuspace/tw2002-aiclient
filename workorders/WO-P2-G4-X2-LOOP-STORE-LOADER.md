# WO-P2-G4-X2-LOOP-STORE-LOADER

**Status:** OPEN · Claude Code · buildable NOW (zero contention)  
**Posted:** 2026-07-26 · parent G4 blocked-on-substrate report

## Goal

Public validated **single-loop loader** in `loops/store.py` (read one taught loop by name; honest empty / missing / unreadable). No send path. No `autoloop` verb.

## Scope

- `tw2002_aiclient/loops/store.py` (+ thin tests)
- Docs/honesty only if README claims change

## Constraints

- Package stays read-only / no keystroke (existing `__init__` pin)
- No `protocol.py` / `daemon.py` / `cli.py` unless announced
- Do not invent writer (`tw record`) — that is X6
- Do not invent player / autoloop — X3/X4

## Accept

Load by name returns validated structure or typed honest miss; unreadable ≠ empty; pins green.

## Proof

STATUS + SHA · targeted pytest.

## Refs

CC G4 STATUS 2026-07-26T03:17:33Z · X2 in M3 six-slice table · `macros.md` schema
