# WO-P2-G4-X4-DAEMON-AUTOLOOP-VERBS

**Status:** OPEN · Claude Code preferred · **blocked until** `protocol.py` free of C.2.1 / sequenced with X1  
**Posted:** 2026-07-26 · M3 slice X4 (stub)

## Goal

Daemon background player + honest arm state + the four autoloop verbs; **only** legitimate production caller of `enter_auto_loop()`. Makes `cockpit/arm.py` truthful (today hardcodes `{"running": False}`).

## Scope

- `protocol.py` / `daemon.py` autoloop verbs + arm field honesty
- Wire to X3 player · no fabricated ARM ON

## Constraints

- Stop-on-unknown · no lying safety surface (arm.py precedent)
- Sequence behind C.2.1 + prefer after X1 if same files
- Do not invent CLI-side do-loop that skips `enter_auto_loop`

## Accept

Verbs + arm state match runtime; sole `enter_auto_loop` caller; suite green; cockpit ARM chip honest.

## Proof

STATUS + SHA · targeted pytest.

## Refs

CC G4 six-slice 2026-07-26T03:17:33Z · cockpit/arm.py · M3 X4
