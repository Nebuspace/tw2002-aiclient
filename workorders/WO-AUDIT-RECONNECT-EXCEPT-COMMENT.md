# WO-AUDIT-RECONNECT-EXCEPT-COMMENT — Annotate reconnect broad-except

> Status: **DRAFT** 2026-07-25 · Zone-A micro-bank · MICRO-SCOUT pin tip `01bac96`  
> Type: docs/polish · Priority: P3 · Lens: L4  
> Refs: `session/session.py:164-167` · CC POLISH Zone-A bank

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
Diff review. Push waits Accept.
