# WO-FIX-TRADE-DRIVER-DOCSTRING-STALE-AUTOPILOT-CITE

**Status:** prose-only tip-caller honesty  
**Branch:** `wo/FIX-TRADE-DRIVER-DOCSTRING-STALE-AUTOPILOT`  
**Seat:** impl-aiclient-h1

## Goal

Stop citing nonexistent tip `autopilot.AutopilotEngine` as `run_chain`'s caller.
Name `session.trade_chain.TradeChainRunner` / bounded-repeat instead.

## Scope

- `tw2002_aiclient/trade_driver.py` docstrings/comments only
- This workorder file

## Accept

- No tip-caller claim names `AutopilotEngine` / `AutopilotLoop` / `tw autopilot` as live.
- Tip callers named with evidence.

## Proof

- Docs/comments only → live-prove `n/a`
- `pytest -n0 tests/test_trade_driver.py tests/test_trade_chain_runner.py` green
