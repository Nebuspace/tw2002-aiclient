# WO-AICLIENT-BUILD-TRADE-FLOAT-STATUS-PRODUCER

**Goal:** Status producer for `trade_float` (working-capital reserve) so
`goals` → `afford_fighters` can see a real float when one exists.
Omit-until-known; never invent a default reserve at play entry.

**Scope:**
- `tw2002_aiclient/trade_float_status.py` (new)
- `tw2002_aiclient/screens.py` / `app.py` (construct + wrap + observe from
  active trade/hold `cash_floor`)
- `tests/test_trade_float_status.py`
- `tests/test_status_vocabulary_guard.py` (delete starved allowlist entry)

**Out of scope:** inventing a tip `DEFAULT_TRADE_FLOAT`; changing
`DEFAULT_CASH_FLOOR` values; buy/EXECUTE paths.

**Accept:**
- `TradeFloatScalars.merge` writes `trade_float` only after `observe`
- Money-path start / status poll feeds `cash_floor` via `_observe_trade_float`
- Vocab guard: `trade_float` no longer starved
- Fail-closed on bad observe values; never clobbers an existing status key

**Proof:**
- `.venv/bin/python -m pytest tests/test_trade_float_status.py tests/test_status_vocabulary_guard.py tests/test_fighter_affordability.py -q`
- `live-prove: n/a` — offline status merge; no login/session money-path change beyond observing an already-armed cash_floor
