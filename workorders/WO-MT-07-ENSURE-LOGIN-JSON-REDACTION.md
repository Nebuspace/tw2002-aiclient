# WO-MT-07-ENSURE-LOGIN-JSON-REDACTION

**Status:** OPEN · Claude Code (diagnosis-first OK)  
**Posted:** 2026-07-25T20:04:13Z

## Goal

Sentinel password absent from ensure/protocol error dict folded to CLI JSON (MT-07).

## Scope

- Ensure/login error path
- New/extended collecting tests (not `pytest.ini`-ignored)

## Constraints

- Secrets Max-gate (`repr` / `get_password`) is **orthogonal** — do not expand into that; stick to ensure JSON sinks.
- Money/classify parked.

## Accept

`returning_password_rejected` / malformed secrets → sentinel absent from returned dict + printed JSON; inject-leak falsification.

## Proof

Collecting pytest + STATUS.

## Refs

- `workorders/AUDIT-MISSING-TESTS.md` MT-07
- LOGIN-REHAB
