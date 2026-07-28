# WO-ADAPTER-CONFIG-GUARDS-LOW — Close bool + ceiling_multiplier guard holes

**Status:** OPEN · BANKED · LOW (folded)  
**Posted:** 2026-07-28T00:15:00Z · banked from WO-CHAIN-DETECT-PORT STATUS  
**Seat:** open  
**Refs:** `tw2002_aiclient/trade_adapter.py` · `TradeAdapterConfig.__post_init__`

## Goal

Two low-severity guard holes found during WO-CHAIN-DETECT-PORT adversarial QA,
folded into one WO:

1. **`bool` passes numeric guards.** `float(True) == 1.0` — a Python `bool`
   satisfies the `isinstance(x, (int, float))` / positivity checks used for
   `pct`/`amount`/`margin` fields where a real float is expected.  Reject `bool`
   explicitly in those guards.

2. **`ceiling_multiplier < 1.0` accepted at config-construction, inverting the
   price curve.** A multiplier below 1.0 makes near-empty ports price *cheaper*
   than near-full — the opposite of the intended curve.  `TradeAdapterConfig.__post_init__`
   already validates `max_hops >= 0`; add `ceiling_multiplier >= 1.0` (or
   `> 0.0` if the canon allows sub-unity) to the same guard block.

## Accept

1. `TradeAdapterConfig(ceiling_multiplier=0.5)` raises `ValueError`.
2. Passing `True` where a numeric price field is expected raises `TypeError` or
   is rejected by the relevant guard.
3. Suite green; STATUS.
