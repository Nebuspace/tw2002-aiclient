# WO-BUILD-CHAIN-DEPLETION-PREDICTOR

**Status:** IN FLIGHT · Cursor · `wo/BUILD-CHAIN-DEPLETION-PREDICTOR`
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ `7b15a7e`
**Refs:** `canon/strategy/port-economics.md` § Route-longevity & depletion predictor (H2) ·
queue-aiclient.md · `chains.py` / `trade_driver.py` / `chain_status.py`

## Goal

Implement the canon `remaining_trades` predictor and feed it into STOP,
explore appetite, and chain down-rank — without autonomous loop rotation
and without inventing stock or hold counts.

## Formula (hypothesis)

```
remaining_trades ≈ min(stock across buy/sell legs) ÷ ship hold count
```

Leg stocks = observed commodity `amount` fields. Hold count = live ship
holds. Incomplete evidence → omit (`None`), never invent.

## Scope

1. Pure module `tw2002_aiclient/chain_depletion.py` (formula, leg extract,
   signals, longevity ranker).
2. `chains.rank_chains_by_longevity` re-export for discovery callers.
3. `ChainScalars.merge` attaches status keys when holds + amounts known:
   `chain_remaining_trades`, `chain_nearing_depletion`,
   `explore_appetite_raised`, `chain_depletion_stop_recommended`.
4. Coach: `chain_nearing_depletion` fires `loop_depleting` (appetite /
   coaching — ranking, not driving).
5. `trade_driver.run_chain` STOPS before the first hop when predicted
   remaining_trades &lt; 1 (`depleted:predicted:…`).
6. Pins in `tests/test_chain_depletion.py`.

## Out of scope

- Autonomous loop rotation (forbidden by canon).
- Plague ~10M ceiling heuristic (separate hypothesis).
- Inventing amounts from class-only ports / density.

## Accept

1. Formula pin: `min(stocks)/holds`.
2. Fail-closed on missing amount / holds.
3. Longevity ranker down-ranks near-depleted chains.
4. Status merge + coach + predicted STOP paths covered by tests / code.
5. Focused pytest green; live-prove **n/a** (offline predictor + guards).

## Proof

```bash
.venv/bin/python -m pytest tests/test_chain_depletion.py tests/test_chains.py -q -n0
```

live-prove: `n/a` — pure/offline; no login path.
