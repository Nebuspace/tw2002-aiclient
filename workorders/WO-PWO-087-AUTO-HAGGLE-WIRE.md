# WO-PWO-087-AUTO-HAGGLE-WIRE — Opt-in auto-haggle in trade_driver

> Status: **DONE** · origin `37fd42d` (#360) · seat `impl-aiclient-cursor` · Accept 2026-08-03  
> Type: harden · PWO-087  
> Tip base: `3726c49` → merged `37fd42d`

## Goal
Wire tip `session/haggle.run_haggle` into `trade_driver._accept_offer`, with **`TradeDriverConfig.auto_haggle` default False** (available, not hard-disabled).

## Scope
- A: `TradeDriverConfig.auto_haggle: bool = False`
- B: `_accept_offer` blank-accept when off; `run_haggle` when on
- C: fair_value seed from unit estimate × qty
- D: tests + tip honesty docs (PREP / inventory / WO-AUTOHAGGLE)

## Constraints
- Default OFF — existing callers unchanged
- No AI path; App sender only
- Desync / no-active → ChainHold

## Accept
1. Default config has `auto_haggle is False`
2. Off path still blank-accepts
3. On path can counter (digit send before accept)

## Proof
`pytest tests/test_trade_driver.py tests/test_haggle.py -n0` · live-prove **n/a** (offline)

## Refs
- Hub GO 2026-08-03T12:33:10Z · Max GO
- Prior: WO-AUTOHAGGLE-GUARDED-RULE (#337)
