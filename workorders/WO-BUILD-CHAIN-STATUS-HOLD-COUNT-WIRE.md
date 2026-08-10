# WO-BUILD-CHAIN-STATUS-HOLD-COUNT-WIRE

**Status:** in flight (impl-aiclient-cursor)
**Priority:** LOW (unused-code tip_check residual after Aug-09 READY exhaustion)
**Depends-on:** none (tip `chains.hold_count_from_status` already exists; screens.py already consumes it)

## Goal

Wire `chain_status.ChainScalars` depletion hold-count reads through the shared
`chains.hold_count_from_status` free function — tip currently keeps a private
duplicate `_hold_count_from_status` whose keys the free-function docstring
already claims to mirror (same class as #659 `recommend_genesis`).

## Scope

- `tw2002_aiclient/chain_status.py` — delegate `_hold_count_from_status`
- `tw2002_aiclient/chains.py` — docstring names product callers
- `tests/test_chain_depletion.py` — spy pin
- this WO file

## Out of scope

- Changing hold-count key preference / fail-closed semantics
- BEST-PAIR / `best_chain` / `best_pair` (already product-wired for bubbles; queue tip-closed false-premise)
- Disposition-ledger edits (hub `.samantha/audit/`)

## Accept

1. `ChainScalars._hold_count_from_status` calls `chains.hold_count_from_status`.
2. Existing depletion merge pin still green (0.25 remaining / nearing flags).
3. Spy test proves the free function is on the product path.

## Proof

```bash
.venv/bin/python -m pytest tests/test_chain_depletion.py tests/test_chains.py -q -n0
```

Live-prove: **n/a** (offline hold-count SSOT; no login/play arm).
