# WO-PWO-106-GENESIS-CONFIRM-SEAM

**Status:** build (PWO-106 Option A)
**Hub GO:** 2026-08-03T13:59:00Z B-Option-A (B-Option-B declined)

## Goal
Ship the armconfirm-reuse default-deny Genesis confirm-to-send seam **without** a Genesis adapter/stub.

## Scope
- `tw2002_aiclient/genesis_confirm.py`
- `tests/test_genesis_confirm.py`
- this WO

## Accept
- Confirm line uses `cockpit.armconfirm` (`LIVE?  y/N`; `y`/`Y` only).
- `genesis_send_if_confirmed` never calls `send` unless disposition is CONFIRM + callable send + non-empty payload.
- Mutation pin: skipped/cancelled confirm → zero transport sends.
- No production caller of `genesis_send_if_confirmed` yet (Option A).
- No stub Genesis adapter.

## Proof
`pytest tests/test_genesis_confirm.py` · live-prove n/a (offline seam; no live send path).

## Out of scope
B-Option-B stub adapter + end-to-end Genesis fire (needs fresh GO).
