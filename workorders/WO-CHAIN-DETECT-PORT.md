# WO-CHAIN-DETECT-PORT — Port chains + trade_adapter onto tw2002_aiclient

**Status:** OPEN · STAGED · **blocked on WO-EXPLORE-AUTOMATION-GATE**  
**Posted:** 2026-07-27T21:35:00Z · Max priority tranche ②  
**Seat:** open  
**Depends:** explore gate green · archive `chains.py` / `trade_adapter.py` as reference  
**Refs:** `canon/strategy/trade-loops.md` · `canon/research/archive-port-patterns.md` · plan `trade-loop-chains-after-explore-20260727.md`

## Goal

Land reborn-package **chain detection** pure logic: hops from port postures → ranked profit chains. No TUI. No live sends.

## Scope

- `tw2002_aiclient/` modules for `chains` + `trade_adapter` (not `twclient`)  
- Rewrite/un-ignore `tests/test_chains.py` + `tests/test_trade_adapter.py`  
- Ranking: hop-count desc, then cr/turn; `MIN_CHAIN_LINKS` floors per canon as **ranking inputs only**

## Accept

1. `longest_profit_chain` / `find_profit_chains` green on synthetic graphs.  
2. `build_trade_hops` fail-closed on incompatible postures.  
3. Zero product keystroke sends from these modules.  
4. PR + STATUS + suite.

## Constraints

- No `trade_driver` autonomous runner · no priority EV picker · no `canon/` drift without DECISION.
