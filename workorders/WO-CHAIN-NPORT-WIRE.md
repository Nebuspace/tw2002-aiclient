# WO-CHAIN-NPORT-WIRE — Wire N-port `chains.py` finder to a product surface

**Status:** BANKED · HIGH · Claude Code preferred · after CHAINS-TUI / pairs path settled  
**Posted:** 2026-07-28T03:23Z · hub bank from CC discovery (Max question)  
**Refs:** CC HEADS-UP 2026-07-28T03:22:21Z · #128 wired 2-port pairs only

## Goal
`tw2002_aiclient/chains.py` is a complete N-port profit-cycle finder (DFS, rank, budget,
execute floors) with tests — and **zero** non-test importers / callers. `build_trade_hops`
has no product callers. Cockpit `L)chains` renders taught macros, not this finder.
Wire producer→consumer→surface (or deliberately retire with honesty if Max chooses drop).

## Accept
1. At least one non-test product path reaches `find_profit_chains` / `rank_chains` (CLI and/or Play/TUI — prefer Play per one-client north-star; CLI ok as secondary diagnostic).
2. Or: Max-ruled retire — delete/archive with STATUS citing unused + tests updated.
3. Do not confuse with taught `L)chains` macros or with #128 pair loops (different units/path).
4. Suite + STATUS; live-prove per surface touched.

## Constraints
Money-path adjacent if it suggests trades. Public-repo safe. Coordinate with `WO-CHAINS-TUI-FULL` / coach trigger so we do not double-build surfaces.
