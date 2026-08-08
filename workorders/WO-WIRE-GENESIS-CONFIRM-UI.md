# WO-WIRE-GENESIS-CONFIRM-UI

**Status:** READY · gated: no
**Posted:** 2026-08-08 · orchestrator HANDOFF (unused-wire tranche 2, background triage)

## Goal
genesis_confirm.py's compose/resolve trio has zero references in app.py/screens.py. Wire it in as the confirm/arm choke-point for Genesis sends -- this ADDS a safety gate, it does not remove one.

## Scope
genesis_confirm.py + app.py/screens.py Genesis send path.

## Accept
The wire is live: the previously-zero-caller symbol now has a real product call site, covered by a test proving the call + effect.

## Proof
Targeted regression + full suite green. live-prove: n/a unless the WO note says otherwise.
