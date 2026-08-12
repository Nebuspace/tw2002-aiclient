# WO-CLEANUP-FIND-PROFIT-CHAINS-DEAD-WRAPPER

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Retire the silent `find_profit_chains` wrapper; product and tests use `find_profit_chains_with_note` only.

## Accept

- `find_profit_chains` removed from `chains.py`.
- Stale docstrings in `trade_adapter.py`, `trade_driver.py`, `session/cli.py` cite `with_note`.
- Tests re-pointed; no product callers remain.

## Proof

```bash
.venv/bin/python -m pytest tests/test_chains.py tests/test_trade_adapter.py -n0 -q -k profit
```

live-prove: n/a (offline refactor).
