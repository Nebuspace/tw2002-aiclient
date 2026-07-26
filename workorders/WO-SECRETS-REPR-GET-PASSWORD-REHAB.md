# WO-SECRETS-REPR-GET-PASSWORD-REHAB

**Status:** OPEN · Claude Code preferred (secrets lane)  
**Posted:** 2026-07-26 (Max carte blanche §C)

## Goal

Rehab secret-adjacent error surfaces: `repr(UnicodeDecodeError)` / `get_password` decode failures / stuck-login wire must **never** leak secret or undecoded bytes into exceptions, CLI JSON, or logs. Typed redacted errors only.

## Scope

- credentials / get_password decode paths
- exception formatting that today may `repr()` decode errors with payload
- stuck-login RX redaction continuity

## Constraints

- Max carte blanche §C is GO — still secrets-lane discipline (CC)
- Orthogonal to MT-07 ensure-JSON (do not merge scopes)
- Tempdir-only destructive tests; never live `secrets.json` chmod games on the operator store

## Accept

Injected undecodable / permission failures → typed redacted path; falsify that payload cannot appear in returned dict / printed JSON / log line; suite green.

## Proof

STATUS + SHA · collecting pytest.

## Refs

`DECISIONS.md` §C · secrets-and-credentials doctrine · LOGIN-REHAB
