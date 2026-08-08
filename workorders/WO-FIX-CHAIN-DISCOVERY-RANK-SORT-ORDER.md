# WO-FIX-CHAIN-DISCOVERY-RANK-SORT-ORDER

**Status:** IN FLIGHT · Cursor · `wo/FIX-CHAIN-DISCOVERY-RANK-SORT-ORDER`  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `7fb6665` · diagnosis `WO-DIAGNOSE-CHAIN-DISCOVERY-LOW-QUALITY-YIELD` / #523  
**Refs:** `canon/strategy/trade-loops.md` § Ranking · `chains.rank_chains` ·
`chain_search.recompute` · `session/cli.py::cmd_chains`

## Goal

Unblock credit-doubling / earn glances on `tw chains`: stop burying best
**2-hop @ 3.5 cr/turn** under **9-hop @ 1.0** when the surface is earning,
without breaking canon hop-count-first ranking for discovery/explore.

## Diagnosis (settled)

`rank_chains` sorts `(len(hops), cr_per_turn)` DESC — correct for priority-
layer / explore per `trade-loops.md` § Ranking. CLI and other earn surfaces
inherit that order via `chain_search.recompute`, so operators see a wall of
long thin loops and miss short higher-yield cycles already in the payload.

## Fix (dual-rank — no DECISION)

1. Keep `rank_chains` = hop-count desc, then cr/turn (canon discovery default).
2. Add `rank_chains_by_yield` = cr/turn desc, then hop-count.
3. `chain_search.recompute(..., rank="hops"|"yield")` — default `"hops"` so
   L)chains / bubble / longest callers stay hop-count-first.
4. Wire `cmd_chains` (`tw chains`) to `rank="yield"` — the earn CLI surface.
5. Tests pin: yield-first tops 2-hop@3.5 over 9-hop@1.0; hop-count ranking
   still available and default.

## Scope

- `tw2002_aiclient/chains.py` — `rank_chains_by_yield`
- `tw2002_aiclient/chain_search.py` — `rank=` param + constants
- `tw2002_aiclient/session/cli.py` — `cmd_chains` uses yield rank
- `tests/test_chains.py` · `tests/test_chain_search.py` · `tests/test_cli_chains.py`
- This WO file

## Constraints

- Do **not** change default `rank_chains` / `find_profit_chains` order.
- Do **not** flip L)chains modal / bubble global order in this WO.
- No DECISION unless a canon edge appears (prefer dual-surface reading).
- Explicit-path commits; no secrets; no operator-home paths; AI never live-drives.

## Accept

1. `rank_chains_by_yield([9h@1.0, 2h@3.5])` → `[2h@3.5, …]`.
2. `rank_chains` / default `recompute` still prefer longer hops first.
3. `tw chains` / `cmd_chains` surfaces yield-first ordering.
4. Focused pytest green; live-prove `n/a` (offline ranking; no TWGS arm).

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_chains.py \
  tests/test_chain_search.py \
  tests/test_cli_chains.py \
  -q -n0
```

live-prove: `n/a` — sort-key / offline CLI listing only.
