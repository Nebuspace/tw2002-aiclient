# WO-CANON-FIX-AUTOHAGGLE-TRADE-ARM-STALE-QUEUE

**Status:** CLOSED (verify-first) · Cursor · tip `b4c8829`
**Seat:** `impl-aiclient-cursor`
**Priority:** LOW
**Gated:** no
**Refs:** queue-aiclient.md ~371 · PWO-087 · #360 `37fd42d` · `trade_driver.py:300`

## Goal

Queue-hygiene: a discovery row claimed auto-haggle trade-arm was still
STAGED / a separate candidate. Tip already ships the opt-in wire.

## Verify-first (2026-08-08)

1. `TradeDriverConfig.auto_haggle: bool = False` at `tw2002_aiclient/trade_driver.py:300`.
2. `_accept_offer` blank-accepts when off; calls `session.haggle.run_haggle` when on.
3. `workorders/WO-PWO-087-AUTO-HAGGLE-WIRE.md` Status **DONE** · merge `#360` / `37fd42d`.
4. ULTRACODE / P6 PREP already mark PWO-087 **LIVE**.

## Scope (this PR)

- This WO markdown (CLOSED with evidence).
- Tip-honesty: `workorders/WO-P8-100-107-strategy-PREP.md` hazard #4 no longer
  calls trade-arm a "candidate".
- Stamp `workorders/WO-STAMP-PWO-087-DONE.md` → DONE if still IN FLIGHT.

## Constraints

- Docs / WO-stamp only. No trade_driver behavior change.
- Default remains OFF (standing safety).

## Accept

1. In-repo text no longer stages auto-haggle trade-arm as unbuilt.
2. Queue row ~371 may flip DONE/CLOSED (hub).
3. live-prove: **n/a** (docs/hygiene).

## Proof

Diff review + tip grep of `auto_haggle` / PWO-087 DONE header.
