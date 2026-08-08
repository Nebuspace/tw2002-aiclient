# WO-WIRE-STUB-STORE-APPROVED-READER

**Status:** READY · gated: no
**Posted:** 2026-08-08 · orchestrator HANDOFF (unused-wire tranche 2, background triage)

## Goal
stub_store.set() has 2 live writers (app.py:2259,2342); stub_store.get() has zero product readers. Wire a consumer -- pairs naturally with the already-queued WO-BUILD-ASSIGN-TRIGGER-REKEY, build together if that's in flight.

## Scope
stub_store.py + its intended consumer (app.py or the assign-trigger-rekey module).

## Accept
The wire is live: the previously-zero-caller symbol now has a real product call site, covered by a test proving the call + effect.

## Proof
Targeted regression + full suite green. live-prove: n/a unless the WO note says otherwise.
