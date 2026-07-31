# WO-TRADE-ADAPTER-BUY-SELL-SPREAD — posture-aware price so Gather pct=100 can yield margin

**Status:** DONE · origin `dd8222f` (#270) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/TRADE-ADAPTER-BUY-SELL-SPREAD`
**Depends:** `main` ≥ `91fa979` (#269 pair-fallback bubbles)

## Why

#269 fixed the dishonest empty bubble when **class pairs** exist. Priced
`ProfitChain` bubbles still stay empty after Gather because:

1. Fresh docks write `pct=100` on every commodity row.
2. `trade_adapter._commodity_price` is **posture-blind** — same pct→price
   curve for buying and selling.
3. `margin = to_price - frm_price` is therefore **0** whenever both sides
   share the same pct.
4. `chains.find_profit_chains` hard-filters `margin > 0` → `no_closed_cycle`.

Measured (academy Sextant, pre-#269): 24 TradeHops, every `margin=0.0`.

Real TWGS has a buy/sell spread at the same stock level. Canon
`port-economics.md` is UNVERIFIED on numbers but asserts a floor and a
stock-driven range — it does **not** require buy-price == sell-price at
identical pct.

## Goal

Teach the estimator a **configurable buy/sell spread** (or asymmetric
curves) so two ports with complementary postures and the **same** pct can
produce `margin > 0`, without inventing live observed unit prices or
weakening the `margin > 0` canon filter.

## Scope

1. **`trade_adapter.py`** — extend `TradeAdapterConfig` with an explicit
   spread knob (e.g. sell-side markup / buy-side discount as fraction of
   floor, or separate multipliers). Document as UNVERIFIED modeling, same
   honesty as `ceiling_multiplier`.
2. **`_commodity_price`** (or a thin wrapper) — must take posture
   (`selling` vs `buying`) into account so buy≠sell at equal pct.
3. **Pins:** same-pct complementary ports → `margin > 0`; opposite-posture
   mismatch still fail-closed; existing tests stay green or intentionally
   updated with rationale.
4. **Do not** mint observed unit-price fields into world-model schema.
5. **Do not** change bubble UI (#269 already falls back to class pairs).
6. Optional: one end-to-end pin that `chain_search.recompute` on a synthetic
   same-pct world returns a non-empty chain (proves priced bubbles can light).

## Out of scope

- Live TWGS price-table introspection / game-data-store wiring.
- Changing `CandidatePair` / class path.
- Arming / approve-scaffold changes.
- `#218` app.py split.

## Constraints

- All numbers via `TradeAdapterConfig` — no new hardcoded magic constants
  outside config defaults.
- Defaults must be conservative and documented UNVERIFIED.
- Public-safe STATUS.
- Live-prove: `n/a` if offline-only estimator (preferred) **or** Cursor safe
  half recompute on existing Gather world showing `chains` non-empty /
  honest still-empty with reason. Never costume.

## Accept

1. Config exposes the spread; default documented.
2. Complementary sell@pct=X / buy@pct=X yields `margin > 0` under default.
3. Same-posture pair still produces no hop.
4. Focused adapter + (optional) chain_search pins green; full offline suite.
5. Live-prove: `n/a` with reason **or** store recompute evidence as above.

## Proof

```bash
pytest -q tests/test_trade_adapter.py tests/test_chains.py
# + new spread pins
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- Hub diagnose 2026-07-31 · Max empty-bubble report · #269
- `trade_adapter.py` · `chains.py` (`margin > 0`) · `canon/strategy/port-economics.md`
