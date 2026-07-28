# WO-ADAPTER-FRESHNESS-FUTURE-TS — Clamp future-timestamp delta in _is_fresh

**Status:** IN PROGRESS · EXECUTE · MED · Cursor-class · impl-aiclient-cursor  
**Posted:** 2026-07-28T00:15:00Z · banked from WO-CHAIN-DETECT-PORT STATUS  
**Seeded for execute:** 2026-07-28T01:36Z · hub  
**Seat:** impl-aiclient-cursor  
**Refs:** `tw2002_aiclient/trade_adapter.py` · `_is_fresh`

## Goal

`_is_fresh` computes `(now - ts).total_seconds() <= max_age_s`.  A **future**
timestamp (clock skew, corrupt write, a record stamped 2099) makes the delta
negative; a negative value trivially satisfies the `<=` bound, so the record
sails through the staleness gate unconditionally.

The module's docstring promises fail-closed on timestamps — a future-stamped
record slipping through is a false promise in a safety docstring.

**Fix:** clamp the age delta to `[0, max_age_s]` before the comparison, or
equivalently: `(now - ts).total_seconds() < 0` → treat as stale (fail-closed).

## Accept

1. A port record whose `last_seen_ts` is in the future is rejected by `_is_fresh`.
2. A record with `last_seen_ts` in the recent past is still accepted.
3. Suite green; STATUS.
