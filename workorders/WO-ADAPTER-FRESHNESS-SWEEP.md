# WO-ADAPTER-FRESHNESS-SWEEP — Every age/freshness site routes through _is_fresh

**Status:** DONE · origin `e7cdbf7` (#138) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28T01:55Z · hub (from CC #128 twin of #131)  
**Seat:** open  
**Depends:** #128 in-lane twin fix (CC) · tip includes `_is_fresh` fail-closed (#131)

## Goal

#131 fixed `_is_fresh` for future timestamps. An **identical hole** lived in
`build_candidate_pairs` as an inline age check (CC execution-proven 2026-07-28).
That twin is handled in #128. This WO sweeps the **class**: every site that
derives freshness or age must not re-implement the predicate.

## Accept

1. Grep/audit: no remaining inline `(now - ts)` freshness decisions outside the
   shared helper (except documented test doubles).
2. Call sites use `_is_fresh` (or one shared helper it owns).
3. **No age aggregation laundering:** `max`/`min`/mean over ages must only run
   on stamps that already passed `_is_fresh` / fail-closed parse. A single
   future stamp must not yield a healthy-looking neighbour age on a pair
   (CC probe: one-future → `observed_age_s=3600` from the other port).
4. Pins for gate + any aggregated `observed_age_s` (or equivalent) field.
5. Suite green; STATUS. live-prove n/a unless product path touches live world load.

## Refs

- CC HEADS-UP 2026-07-28T01:44:38Z · STATUS 01:52:57Z
- Hub ACK sharpening sweep Accept (aggregation launder)
