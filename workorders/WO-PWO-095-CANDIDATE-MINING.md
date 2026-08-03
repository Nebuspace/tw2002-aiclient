# WO-PWO-095-CANDIDATE-MINING — Candidate mining (no LLM)

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T05:06:57Z  
> Type: build · PWO-095  
> Tip base: `2644499` (PWO-094 LIVE)

## Goal
Port the deterministic profit-miner: sliding-window over the reborn ledger → inert drafts under `state/skills/_drafts/`. Ranks candidates to *propose*; never scores a live action to play.

## Scope
- A: `tw2002_aiclient/miner.py` (new — port from archive `twclient/miner.py` against reborn ledger + draft write)
- B: `tests/test_miner.py` (fixture ledger + draft stats/start-anchor + redacted skip + never-promote)
- C: dry-run CLI (`python -m tw2002_aiclient.miner --ledger … --drafts …`)
- D: ULTRACODE + P7 PREP tip honesty → 095 LIVE
- E: this WO file

## Constraints
- Pure ledger read + draft write — no session send / protocol / connection imports in the miner module
- Drafts never auto-promote (`blessed` / non-draft save stays human-only)
- Skip windows containing `<redacted>`; wildcard bare numerals to `<NUM>` for grouping only
- No live TWGS arm

## Accept
1. Dry-run over a synthetic ledger produces expected draft(s) with correct stats / start-anchor
2. Draft never auto-promotes
3. No live-connection code path in the miner

## Proof
`pytest tests/test_miner.py` · CLI dry-run showing draft output · CI suite · live-prove **n/a** (offline miner)

## Refs
- Canon: `canon/engine/candidate-mining.md`
- Ledger: `tw2002_aiclient/ledger.py` (PWO-094)
- Archive twin: `archive/pre-rebirth-2026-07-23/code/twclient/miner.py`
- Hub GO: orchestrator 2026-08-03T05:06:57Z
