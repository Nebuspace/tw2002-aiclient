# WO-WIRE-DENSITY-SCAN-CONSUMER

**Status:** READY · gated: no
**Posted:** 2026-08-08 · orchestrator HANDOFF (unused-wire tranche 2, background triage)

## Goal
density_scan write side shipped (PR #537); zero read consumers in sector_explore.py/formations.py. Wire the decoded value in as an explore-ranking input (densest-sector scoring), replacing/augmenting the current graph-degree-only heuristic.

## Scope
sector_explore.py and/or formations.py ranking logic; world_model's density_scan reader.

## Accept
The wire is live: the previously-zero-caller symbol now has a real product call site, covered by a test proving the call + effect.

## Proof
Targeted regression + full suite green. live-prove: n/a unless the WO note says otherwise.
