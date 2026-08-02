# WO-BANNER-STAMP-SWEEP-COACH-CHAIN

**Status:** DONE · origin `3896346` (#286) · tip-honesty stamp 2026-08-02 (sweep landed on main; banner was stale READY)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/BANNER-STAMP-SWEEP-COACH-CHAIN`
**Depends:** `main` ≥ `1bcd3c8`

## Goal

Stamp stale **READY** / **OPEN · EXECUTE** banners whose product already
landed on `main` (coach · status · chain-bubble · gather · trade-adapter
wave #255–#270). Same class of miss as #284 autonomy stamp sweep.

## Tip-check table (hub pre-verified 2026-07-31)

| WO | Tip SHA | PR |
|---|---|---|
| TEACHBAND-L-CHAINS | `8352f3e` | #255 |
| PLAY-CHAIN-BUBBLE-VIZ | `fb33f5b` | #256 |
| CHAIN-BUBBLE-PORT-CLASSES | `4d26eac` | #257 |
| COACH-LOOP-DEPLETING-TRIGGER | `c49819b` | #258 |
| COACH-HAS-PORT | `fc39277` | #259 |
| COACH-DEAD-END-COUNT | `df862ad` | #260 |
| STATUS-FIGHTERS-ABOARD | `7397396` | #261 |
| STATUS-CREDITS | `fb4cdf8` | #262 |
| COACH-EXPLORE-MODE | `ecc42f7` | #263 |
| COACH-ENGINE-DOC-SYNC | `cdf3797` | #264 |
| PLAY-EXPLORE-GATHER-DEFAULT-ON | `243a175` | #265 |
| CHAIN-BUBBLE-PAIR-FALLBACK | `91fa979` | #269 |
| TRADE-ADAPTER-BUY-SELL-SPREAD | `dd8222f` | #270 |
| TEST-TIMING-ASSERT-ORDER | meta-test on main (`tests/test_timing_assert_order.py`) | #140 bank + landed |

## Scope

- Docs-only: flip each banner to **DONE · tip `<sha>` · #<N>** (or equivalent).
- Re-verify each tip is ancestor of `origin/main` before stamping.
- Do **not** invent product work. Skip any row that fails tip-check.

## Accept

1. Listed WO files no longer claim READY/OPEN EXECUTE when tip is on main.
2. No product/code changes.
3. live-prove **n/a**.

## Proof

`git merge-base --is-ancestor <sha> origin/main` per row · STATUS lists stamped paths.

## Refs

- #284 autonomy stamp pattern · IDLE-KICK READY=0 honesty
