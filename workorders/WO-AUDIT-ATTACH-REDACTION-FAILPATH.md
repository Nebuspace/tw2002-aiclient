# WO-AUDIT-ATTACH-REDACTION-FAILPATH

**Status:** DONE · origin `79c9bf5` (MT-01 fail-path + falsification; suite teeth on BrokenPipe)  
**Posted:** 2026-07-25T15:27:10Z

## Goal

Extend attach-redaction suite so **failure-path** payloads cannot slip past green (F6 lesson — inject stayed 8/8).

## Scope

- `tests/test_attach_redaction.py`
- Thin product fix **only if** a real hole is proven; announce before touching non-test paths

## Constraints

Keep success-path falsification teeth · no weaken spectate/canary · secrets doctrine.

## Accept

At least one red→green proof that a failure-path / error-path leak would fail the suite; suite green.

## Proof

STATUS + SHA · hub lands.

## Refs

- AUDIT ACTIVE row · F6 PROCESS-NOTE · `fec3ffe` tip family
