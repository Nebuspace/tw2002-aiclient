# WO-TRADE-PARTIAL-BACKOFF

**Status:** DONE · origin `183ac8e` (#302) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/TRADE-PARTIAL-BACKOFF`
**Depends:** `main` ≥ `13a6ecf` · #299 refuse LOGS

## Why

Operator sees loop:
1. `App-armed — starting trade {long route}… (Port Trade·ON)`
2. `App-armed trade did not start — chain_discovery_partial`
3. repeat every idle tick while still **undocked in a sector**

`trade_chain.start` refuses when `chain_search.recompute(...).truncated` (`session/trade_chain.py` ~170–171). `_autonomy_auto_fire` still picks ungated `run_chain` from FOCUS + bubble subject and retries ~1 Hz with no cooldown — honest LOGS, bad product (spam + no trade).

## Goal

Stop the start/refuse LOGS loop; only auto-fire trade when discovery is complete enough to arm; keep exploring/gathering under Port Trade·ON until then.

## Scope

1. **Preflight:** Before calling `trade_chain_start` (and ideally before painting `starting trade…`), detect truncated/partial discovery (same condition as the runner, or a shared helper). If partial → **do not** start; optional one quiet status or single LOGS line with cooldown — never per-tick spam.
2. **Backoff:** After `chain_discovery_partial` (and similar non-transient refuses: `chain_identity_stale`, `chain_plan_invalid`), suppress auto-fire retries for a cool-down (e.g. ≥30–60s or until map/discovery growth / sector change). Pins for no multi-fire within cooldown.
3. **Prefer explore:** While Port Trade·ON and discovery partial / no executable complete chain, App-armed path should lean explore/gather (existing explore kick) rather than hammering trade start. Do not invent dock without discovery.
4. Pins: unit on auto_fire + optional policy; no stuck starting; partial → one refuse then silence for cooldown.
5. This WO on the branch.

## Out of scope

#283 · teachband · rewriting chain_search EV · #301 focus pty (parallel OK if disjoint files — prefer this seat serial: finish or HOLD #301 first if mid-flight).

## Accept

1. Live-shaped idle loop with truncated discovery does **not** flood LOGS with starting/did-not-start every second.
2. Auto trade only attempts start when discovery is non-truncated (or documents why).
3. Focused pins green; suite green; live-prove diversity if money-path (hub may require Max GO) — else STATUS `NOT-ATTEMPTED` honestly.

## Proof

pytest policy_auto + trade_chain refuse pins; STATUS. No self-merge.

## Refs

`session/trade_chain.py` `chain_discovery_partial` · `app._autonomy_auto_fire` · Max report undocked sector loop
