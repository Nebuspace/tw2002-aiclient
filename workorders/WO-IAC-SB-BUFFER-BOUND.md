# WO-IAC-SB-BUFFER-BOUND

**Status:** OPEN · HANDOFF · Cursor  
**Posted:** 2026-07-27 · from `audit/session-iac-audit-20260727.md` I-01  
**Seat:** impl-aiclient-cursor (volume · mechanical)  
**Depends:** `WO-AUDIT-SESSION-IAC` DONE (`0aa8aa0`)

## Goal

An unterminated telnet subnegotiation (`IAC SB` without matching `IAC SE`) must **not**
swallow the entire stream forever. Cap `_sb_buf`, abandon the subnegotiation on overflow,
return to data state, and surface the event.

## Why

Audit I-01 (MED): one corrupt byte pair wedges `_STATE_SB` permanently; after 1e6 ordinary
game bytes the buffer held 1e6+1 and the terminal received **zero**. Meanwhile
`rx_count`/`last_rx` still advance → liveness looks healthy while the screen is frozen.

## Scope

- `tw2002_aiclient/session/iac.py` (or wherever `_sb_buf` / `_STATE_SB` live — audit cites `iac.py`)
- `tests/` — unit: unterminated SB + flood → cap hit, state returns to DATA, subsequent bytes paint

## Out of scope

- `connection.py` `rx_count`/`last_rx` semantics → separate `WO-CONN-RX-COUNTERS-VS-TERMINAL-FEED`
- I-02 reader-thread honesty → `WO-CONN-READER-THREAD-DEATH-HONESTY` (CC)
- Outbound IAC escape / option state table

## Accept

1. Cap `_sb_buf` (≤1 KiB is fine; document the constant)
2. On overflow: abandon SB, return to `_STATE_DATA` (or equivalent), surface an event/log — do **not** hang forever
3. After abandon, subsequent ordinary game text reaches the terminal again
4. Pin: unterminated SB + flood → assert buffer ≤ cap · state recovered · bytes after flood delivered
5. No invent of new screen classes; no connection.py counter redesign

## Proof

```text
pytest <new_or_extended_iac_tests> -q -n0
# mutation: remove the cap → pin goes red
```

## Refs

- `audit/session-iac-audit-20260727.md` §I-01
- Cap rationale: TWGS subnegotiations are tiny; 1 KiB is generous
