# WO-CONN-READER-THREAD-DEATH-HONESTY

**Status:** READY  
**Posted:** 2026-07-27 · from `audit/session-iac-audit-20260727.md` I-02  
**Seat:** impl-claudecode-aiclient (Fable OK)  
**Depends:** `WO-AUDIT-SESSION-IAC` DONE (`0aa8aa0`)

## Goal

If the daemon reader thread dies because `negotiator.feed()` (or the loop body) raises, the
connection must **not** keep advertising `connected=True`. Mark down, log, fail closed.

## Why

Audit I-02 (MED): `feed()` is unwrapped in `_reader_loop`; `connected = False` sits after
the `while`. Proven: thread dead, `connected` still `True`, stderr traceback invisible in
curses. Blast radius = any future exception in negotiation, not only I-03's >255 dimension.

## Scope

- `tw2002_aiclient/session/connection.py` — wrap reader loop body; on unexpected exception set
  `connected=False` (and log) before the thread exits
- `tests/` — negotiator stand-in that raises → assert thread dead **and** `connected is False`

## Out of scope

- I-01 SB buffer cap → `WO-IAC-SB-BUFFER-BOUND` (Cursor)
- I-03 outbound escape / dimension validation (latent until NAWS reports real size)
- Settle / `last_rx` redesign

## Accept

1. Unexpected exception in reader loop → `connected` is `False` when the thread is gone
2. Event/log surfaces the failure (operator-visible path or durable log — no silent death)
3. Pin: raising negotiator → thread not alive · `connected is False`
4. Happy-path reads unchanged (no false disconnect on clean traffic)
5. Disjoint from Cursor IAC SB WO — do not edit `iac.py` buffer logic here

## Proof

```text
pytest <reader_death_tests> -q -n0
# mutation: remove the except / connected=False → pin goes red
```

## Refs

- `audit/session-iac-audit-20260727.md` §I-02 (`connection.py:137-156`)
