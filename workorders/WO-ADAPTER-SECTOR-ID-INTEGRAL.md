# WO-ADAPTER-SECTOR-ID-INTEGRAL — Validate sector_id instead of truncating

**Status:** OPEN · EXECUTE · MED · Cursor-class  
**Posted:** 2026-07-28T00:15:00Z · banked from WO-CHAIN-DETECT-PORT STATUS  
**Seeded for execute:** 2026-07-28T01:44Z · hub  
**Seat:** impl-aiclient-cursor  
**Refs:** `tw2002_aiclient/trade_adapter.py` · `_fresh_ports` / port-record loop

## Goal

`int(rec["sector_id"])` **truncates** instead of validating: on-disk values
`10.9` and `10.1` both become key `10`, and the second record silently clobbers
the first.  This is a silently-wrong-answer defect: one real sector's trade data
vanishes, non-deterministically by write order.

**Fix:** assert or raise when `sector_id` is not already an integer value (e.g.
`if sector_id != int(sector_id): raise ValueError(...)` or equivalent schema
validation).  Do not truncate.

## Constraints

- Do not touch `wo/CHAIN-DETECT-WIRE` / #128
- Leave `WO-ADAPTER-CONFIG-GUARDS-LOW` for a later HANDOFF
- No new dependencies

## Accept

1. A port record with a non-integral `sector_id` (e.g. `10.9`) raises a clear
   error rather than silently mapping to `10`.
2. A port record with an integral `sector_id` (e.g. `10` or `10.0`) is accepted
   as before.
3. Suite green; STATUS.

## Proof

Offline suite + focused `test_trade_adapter` pins. live-prove **n/a** (offline adapter).
