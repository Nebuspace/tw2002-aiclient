# WO-AUDIT-CTRL-RBRACKET-APP-HOLD — Rule Ctrl-] from App-hold

> Status: **DRAFT** 2026-07-25 · AUDIT-OKF-6LENS · **PARKED** pending hub/Max  
> Type: verify/build · Priority: P1 · Lens: L5  
> Refs: findings `DOC-GAP-CTRL-RBRACKET-FROM-APP-HOLD` · tip `d4a8829` kernel pin

## Goal
Replace accidental no-op for Ctrl-] while in App-hold with a **deliberate** ruled behavior (e.g. no-op stay App-hold, or transition to Spectate) and update canon.

## Scope (after Max/hub ruling)
- A: `app.py` / play loop — implement ruled transition only
- B: tests — flip kernel pin from “accidental” to Accept-driven
- C: canon + findings — sign DOC-GAP closed

## Constraints
Do **not** build until hub posts GO with chosen semantics. Do not invent Human→App keys. Do not steal 057 Spectate detach semantics without ruling. Tripwire untouched.

## Accept
Documented behavior matches tests; findings row CLOSED or superseded; Esc≠detach preserved.

## Proof
FakeDaemon matrix · suite fingerprint · STATUS. Push waits Accept.

## Refs
061 kernel STATUS · `test_cockpit_attach.py` unruled pin · `spectate-and-attach.md`
