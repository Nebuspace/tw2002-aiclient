# WO-CANON-DRAFT-GENESIS-COUNT-STATUS-PRODUCER-STALE — correct stale "no producer" note

**Status:** IN FLIGHT · Cursor · `wo/CANON-DRAFT-GENESIS-COUNT-STATUS-PRODUCER-STALE`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Fix `canon/engine/coaching-engine.md` claim that `genesis_count` has no status
producer — tip already emits it via `world_stats.py` and consumes it in
`cockpit/decisions.py`.

## Accept

1. Divergence note no longer says "Still no status producer: genesis_count".
2. Names tip producers (`world_stats` / `decisions`).
3. live-prove `n/a` (docs-only).

## Refs

- `tw2002_aiclient/world_stats.py` `GENESIS_COUNT_KEY` · `cockpit/decisions.py:238`
