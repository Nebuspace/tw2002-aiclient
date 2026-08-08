# WO-WIRE-BULK-UPSERT-CIM-INGEST

**Status:** READY · gated: no
**Posted:** 2026-08-08 · orchestrator HANDOFF (unused-wire tranche 2, background triage)

## Goal
world_model.bulk_upsert has test-only callers, zero product call sites. Wire it into the appropriate ingest path so bulk world-model writes actually use the batched primitive.

## Scope
world_model.py ingest call sites.

## Accept
The wire is live: the previously-zero-caller symbol now has a real product call site, covered by a test proving the call + effect.

## Proof
Targeted regression + full suite green. live-prove: n/a unless the WO note says otherwise.
