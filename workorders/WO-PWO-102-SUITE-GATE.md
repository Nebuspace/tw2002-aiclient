# WO-PWO-102-SUITE-GATE — Un-ignore trade_driver depletion STOP in default suite

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T02:56:52Z  
> Type: test-gate / tip honesty · PWO-102  
> Tip base: `c2ca47a`

## Goal
Close PWO-102 PARTIAL: prove trade-loop depletion STOP in the **default** suite by un-ignoring `tests/test_trade_driver.py` (already green offline).

## Verify-first (done)
- `pytest.ini` ignored the file because WO-CHAIN-DETECT-PORT scoped out the autonomous runner — not because tests were broken.
- Direct run: **26 passed** including `test_depleted_stock_stops_the_chain_cleanly` (`stop_reason == "depleted:0:buy:Fuel Ore"`).
- FakeChainSession only — no network / no live TWGS.

## Scope
- A: remove `--ignore=tests/test_trade_driver.py` + comment refresh in `pytest.ini`
- B: ULTRACODE PWO-102 → **LIVE** + Phase-8 PREP tip refresh
- C: this WO file

## Constraints
No product invention. Hold 092 / 111 / 113. Live TWGS arm remains Max-gated (not claimed). Auto-haggle OFF residual stays #337 follow-on.

## Accept
Default suite collects and greens `test_trade_driver.py`; depletion STOP covered; inventory/PREP match tip.

## Proof
`pytest tests/test_trade_driver.py` green · default suite includes the file · PR checks.
