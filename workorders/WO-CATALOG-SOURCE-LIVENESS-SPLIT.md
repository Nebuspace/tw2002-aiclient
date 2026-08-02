# WO-CATALOG-SOURCE-LIVENESS-SPLIT — Separate provenance from TCP liveness

**Status:** DONE · origin `acb2832` (#146) · tip-honesty stamp 2026-08-02 (product on main; banner was stale SEAT-DONE awaiting Accept)
**Posted:** 2026-07-28T02:31Z bank · EXEC overnight after #145 · seat STATUS 2026-07-28T04:18Z  
**Refs:** #128 live-prove probe · live-prove-pushback · overnight carte blanche

## Goal
Catalog `status` must not conflate **listing provenance** (`listed` / `listed_bbsguide`) with
**reachability**. Split fields so operators/scripts cannot treat `connectable: 0` as "no TWGS".

## Accept
1. Inventory (and any summary printer) exposes distinct provenance vs liveness fields
   (e.g. `source`/`listed_*` vs `liveness`/`last_probed_utc`/`tcp_open`).
2. Existing `connectable` either removed, renamed, or documented as provenance-only with a
   pin that live-prove planning does not treat it as TCP truth.
3. Optional: safe one-shot TCP probe script writing liveness only (no game turns).
4. Suite/docs pins + STATUS. live-prove n/a (config/schema) unless probe script is exercised.

## Constraints
Public-repo safe — no tailnet IPs/ssh runbooks. No secrets. Explicit paths.
Do not touch chains (#144) / explore runner internals unless catalog loader requires.
