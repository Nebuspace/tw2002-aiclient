# WO-AICLIENT-DOC-CHAIN-UNITS-HOP-STEP-SEMANTICS

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1

## Goal

Document the hops-vs-steps split owned by `chain_units.py` (library-row
`steps` wire field) and why it lives outside `coach_engine`.

## Changes

- New section in `canon/strategy/trade-loops.md` (natural owner for chain
  arithmetic / library-row shape)
- Citation for `chain_units.py`
- Cross-link from `canon/engine/coaching-engine.md` (consumer, not owner)

## Accept

- [x] Canon names `chain_units.py` as sole hops/steps decision
- [x] Table: discovered/presence_seed → hops; recorded/mined → steps
- [x] States why outside `coach_engine` + points at `ChainScalars` / GOALS
- live-prove: **n/a** (canon only)

## Proof

```bash
rg -n 'chain_units|hops vs keystroke|unit_for_source' \
  canon/strategy/trade-loops.md canon/engine/coaching-engine.md
```
