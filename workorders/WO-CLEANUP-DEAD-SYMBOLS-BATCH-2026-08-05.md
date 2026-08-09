# WO-CLEANUP-DEAD-SYMBOLS-BATCH-2026-08-05

**Status:** DONE (residual — branch `wo/CLEANUP-DEAD-SYMBOLS-RESIDUAL`)

## Goal

Retire dead symbols with zero product callers: `run_live_crawl`, `longest_profit_chain`.

## Proof (tip `7f8e6a9`)

| Symbol | Product callers under `tw2002_aiclient/` |
|---|---|
| `menu.crawl_driver.run_live_crawl` | 0 |
| `chains.longest_profit_chain` | 0 |

`crawl_driver.py` had no other exports — entire module was `run_live_crawl` plus private helpers (`CrawlSafetyError`, `CrawlAborted`, `_wrap_session_factory`, logging helpers). File deleted, not hollowed.

**Out of scope:** `canon/doctrine/action-safety-guards.md` (tip-closed WO), `adapters.py` REASON_*, `port_economics` hypothesis helpers.

## Paths

- `tw2002_aiclient/menu/crawl_driver.py` — deleted
- `tw2002_aiclient/chains.py` — remove `longest_profit_chain`
- `tw2002_aiclient/trade_adapter.py`, `trade_driver.py` — docstring only
- `tw2002_aiclient/action_safety.py` — drop `crawl_sacrificial_gate` row (forced by delete)
- `data/coach/strategies.json` — `top_profit_chain` id + surviving API in steps
- `tests/test_crawl_driver.py` — deleted
- `tests/test_chains.py`, `tests/test_trade_adapter.py`, `tests/test_cockpit_fold.py`
- `tests/test_menu_crawl_chokepoint.py`, `tests/test_secrets_store_redaction.py`, `tests/test_mode_badge_vocabulary.py` — forced by delete
- `tests/test_action_safety_coverage.py` (via map intact)
- `canon/strategy/trade-loops.md`, `canon/research/archive-port-patterns.md`, `canon/testing/*` (test-crawl-driver case retired)

## Accept

1. No `run_live_crawl` or `longest_profit_chain` under `tw2002_aiclient/`.
2. Focused pytest green on touched suites.
