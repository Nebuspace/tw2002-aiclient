# WO-PTY-DRIVE-HOIST — Shared PTY drive loop for cockpit Layer-B tests

**Status:** OPEN · READY  
**Posted:** 2026-07-27T15:12:00Z · hub queue refill after CONN PTY  
**Seat:** open — prefer Cursor volume  
**Depends:** `main` ≥ `49337ff` (CONN PTY + covermeter/arm/teachband/liveness PTY suites)  
**Refs:** CC CONN STATUS banked follow-on · `tests/pty_helpers.py`

## Goal

Deduplicate the ~150-line PTY drive loop now copied across **5** suites (arm · liveness · teachband · covermeter · conn) into `tests/pty_helpers.py` (or one shared helper) without weakening Accept pins.

## Scope

- Extract shared drive/bootstrap helper used by the five suites
- Each suite keeps its own assertions / mutation pins
- No product (`tw2002_aiclient/`) behaviour change

## Constraints

- Tests-only PR; suite count must not drop; green before/after
- Do not weaken wire-gap or content assertions while refactoring
- Prefer smallest helper surface; match existing `pty_helpers` style

## Accept

1. Five suites call shared helper; duplicated drive block removed or trivial.
2. Full suite green; spot-check wire-sweep still PINNED for conn + coverage_meter.
3. PR + STATUS.

## Proof

`pytest` on the five modules + suite CI.
