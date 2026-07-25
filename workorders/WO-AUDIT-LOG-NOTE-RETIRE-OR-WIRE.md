# WO-AUDIT-LOG-NOTE-RETIRE-OR-WIRE — logging_util.log_note fate

> Status: **DRAFT** 2026-07-25 · from CC POLISH Zone-A 🟠 DECISION · tip `88004d8`  
> Type: cleanup / decision · Priority: P2 · Lens: L4 / L6  
> Refs: `session/logging_util.py` `log_note` · zero production callers

## Goal
Hub/Max pick: **wire** `log_note` into a real call site with Accept, or **retire** the dead helper. No silent keep.

## Scope
- A: Decision recorded in STATUS / findings
- B: Either delete + test cleanup, or one production wire + proof
- C: Do not invent AUTO-LOOP consumer (that path is scheduled elsewhere)

## Constraints
No seat-key. No invent Phase-5. Push waits Accept after ruling.

## Accept
Either zero dead exports, or one documented live caller with test.

## Proof
`rg log_note` · STATUS. Push waits Accept.

## Refs
CC Zone-A DECISION @ 05:27:02Z · hub park for ruling
