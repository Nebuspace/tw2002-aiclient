# WO-AUDIT-RECONNECT-EXCEPT-COMMENT — Annotate reconnect broad-except

> Status: **DRAFT** 2026-07-25 · Zone-A micro-bank · tip `00cb9e8`  
> Type: docs/polish · Priority: P3 · Lens: L4  
> Refs: CC POLISH Zone-A bank · hub optional micro list

## Goal
Comment the intentional broad-except on reconnect path: why it is wide, what is logged, what must never leak (secret/payload text).

## Scope
- A: reconnect module comment only (path confirmed at execute)
- B: no catch-narrowing in this micro WO (that would be a separate harden)

## Constraints
Comment-only. No behavior change. No attach/seat-key. Cipher: do not log exception text that may echo server payloads.

## Accept
Reader sees why the except is broad and what observability exists without opening a harden ticket by accident.

## Proof
Diff review. Push waits Accept.
