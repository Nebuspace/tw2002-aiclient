# WO-BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER

**Status:** DONE — PR #637 merged → main @ `22dfe7f3`  
**Max GO:** 2026-08-09 (sacrificial only)  
**HANDOFF:** orchestrator 2026-08-09T13:28Z

## Goal

Give the autopilot a bounded-repeat driver that re-arms `run_chain` automatically
instead of stopping after one 2-hop cycle (ADR-003 one-pass-by-design), so a
sacrificial profile can pursue a profit target / credit-doubling without manual
re-arms.

## Scope

- New module `tw2002_aiclient/bounded_repeat_trade_chain_driver.py`
- Wire through `session/trade_chain.py` + protocol + `tw chain start` CLI
- Unit tests with mocked chain results (no live turns)

## Constraints

- Sacrificial profiles only when `pass_count > 1`
- No new deps
- Defense-in-depth: pass-count ceiling + per-re-arm X5 floor + per-re-arm profit_target

## Accept

1. Bounded-repeat driver mirrors `is_armed` / `should_abort` / fail-closed floor shape
2. Re-arms up to pass-count ceiling (default 10, overridable, hard ceiling 50)
3. Before each re-arm: X5 floor + profit-target halt; first trip wins
4. Not armed for real player accounts
5. CLI exposes `--profit-target` and `--pass-count`
6. Unit tests green (mocked)
7. PR from `wo/BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER`
8. Live sacrificial prove when tools/profiles available; else honest NOT-ATTEMPTED

## Proof

- `pytest tests/test_bounded_repeat_trade_chain_driver.py tests/test_cli_trade_chain_wiring.py tests/test_trade_chain_runner.py`
- Live: sacrificial `tw chain start --pass-count …` when daemon/profile available

## Refs

- ADR-003:33-42 · PR #555 profit-target · `trade_driver.run_chain` · `stardock_hold_driver.py`
- session.py credits supervision (WO-P2-G4-X5)
