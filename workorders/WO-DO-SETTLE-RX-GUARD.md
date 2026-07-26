# WO-DO-SETTLE-RX-GUARD

**Status:** DONE · origin `977b923` (+ hoist comment `79b2978`)  
**Posted / GO:** 2026-07-25T17:47:11Z · Accepted 18:21:38Z

## Goal

`do`/`read` called `wait_settle` with **no** `rx_count` on prompt branch → stale settle at t=0 when awaited prompt equals pre-send prompt. Mirror `send_and_confirm` on `do`; leave `read` t=0-on-present.

## Scope

`do` path rx_count guard; `read` untouched (pin it).

## Accept

`do` carries rx_count guard; timeout still governs; echoed-keystroke byte-counter caveat documented as deliberate; settle suites green.

## Proof

Origin `977b923`; spot-proved do-guard + settle suites 43 passed.

## Refs

- Hub bank @ 17:45:01Z · GO @ 17:47:11Z
- Follow-on: WO-SEND-CONFIRM-RX-DEDUP (outer copy cleanup)
