# WO-CHAIN-WORK-BOUND

## Goal

Bound the expensive pre-output work in `trade_adapter.build_trade_hops` so
the cockpit's automatic chain refresh cannot freeze for seconds or minutes
on a commodity-rich explored world.

## Scope

- `tw2002_aiclient/trade_adapter.py`
- `tests/test_trade_adapter.py`

## Constraints

- Make the smallest deterministic change; do not touch `app.py`,
  `cockpit/live_refresh.py`, chain UI, execution/arming, canon, or dependencies.
- `max_hops` currently bounds output only. Add a configurable non-wall-clock
  budget that bounds expensive route-search work before the complete
  candidate list is built.
- Prefer cheap compatibility/amount/price filtering and deterministic ranking
  before spending route-search budget. Reuse a one-source routing result when
  that is smaller and demonstrably bounded.
- Preserve existing fail-closed posture: unknown routes, malformed rows,
  non-positive turns, and unpriced commodities never become hops.
- Within budget, preserve existing hop membership, margin ordering, and notes.
  When the work budget truncates discovery, return an explicit note: absence
  is not established and the result is not exhaustive.
- Validate the new budget like `max_hops`: reject booleans, non-integers, and
  negative values. No timing-based production cutoff and no flaky wall-clock
  test.

## Accept

1. A deterministic configurable budget limits expensive route-search work;
   increasing compatible port pairs cannot exceed that limit.
2. A unit test uses a spy/counter (not elapsed time) to prove the bound, and
   proves the same fixture returns byte-for-byte-equivalent results across
   repeated calls.
3. A truncation pin proves the note is present and honestly describes an
   incomplete search; a within-budget pin proves legacy output/note behavior
   is unchanged.
4. Zero budget is valid and performs zero route searches; invalid budget
   types/values fail at config construction.
5. Existing trade-adapter tests and the full offline suite pass.

## Proof

```bash
pytest -q tests/test_trade_adapter.py
pytest -q tests
```

Report the counter evidence (configured budget, compatible candidates, actual
expensive route searches) in STATUS. Live prove is `n/a`: this is pure,
offline adapter work with no transport/session/runtime action.

## Refs

- `tw2002_aiclient/cockpit/live_refresh.py` lines 12-45 (measured 220 s cliff;
  output cap does not bound work)
- `tw2002_aiclient/trade_adapter.py` `build_trade_hops`
- `canon/strategy/trade-loops.md` (finder is read-only suggestion; operator
  remains sovereign)
- Depends on merged #228 (`5767411`)
