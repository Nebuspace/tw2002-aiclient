# WO-AUDIT-RECONNECT-EXCEPT-COMMENT — Annotate reconnect broad-except

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`19a0a27`** (CC · rebased onto Cursor `3b32300`) · docs stamp Cursor  
> Type: docs/polish · Priority: P3 · Lens: L4  
> Refs: `session/session.py:164-167` · CC POLISH Zone-A bank

## Tip verdict
**DONE** on origin `19a0a27` — `Session.reconnect()` broad-except carries intentional doctrine comment (dead-socket close must not block reconnect; silence / no `str(e)` log deliberate). AST-identical to pre-comment tip (behavior unchanged). Hub Accept @ 09:40:55Z · CC STATUS-DONE @ 09:43:49Z (`19a0a27` on origin).

## Scout pin (origin `01bac96`)
`Session.reconnect()` tears down via `self.conn.close()` under a bare `except Exception: pass` at **`tw2002_aiclient/session/session.py:164-167`** — swallows any close failure before building a fresh `TelnetConnection`. No comment today explaining why the except is intentionally broad or that nothing may be logged (Cipher: no exception text).

## Goal
Comment that intentional broad-except: why it is wide (dead-socket close must not block reconnect), what is (not) logged, what must never leak (secret/payload text).

## Scope
- A: comment only at `session/session.py:164-167` (and nearby docstring if needed)
- B: no catch-narrowing in this micro WO (that would be a separate harden)

## Constraints
Comment-only. No behavior change. No attach/seat-key. Cipher: do not log exception text that may echo server payloads.

## Accept
Reader at `session.py:164-167` sees why the except is broad and that silence (no log of `str(e)`) is deliberate — without opening a harden ticket by accident.

## Proof
STATUS SHA `19a0a27` on origin. Push waits Accept (product already SHIPped).
