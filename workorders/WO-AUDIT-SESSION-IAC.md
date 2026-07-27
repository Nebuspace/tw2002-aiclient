# WO-AUDIT-SESSION-IAC — Honesty audit of session/iac.py

**Status:** DONE · report `audit/session-iac-audit-20260727.md` · CC (re-routed from Cursor 2026-07-27 during usage/Shell outage) (was READY · MED · Cursor)
**Posted:** 2026-07-26
**Seat:** Cursor (read-only; no product changes)

## Goal

READ-ONLY honesty audit of `tw2002_aiclient/session/iac.py` — the same lens applied to
`session/env.py` (WO-AUDIT-SESSION-ENV).  Surface:

- Docstrings / comments that contradict the code
- Functions that claim to do X but do Y (or nothing)
- Silent failures / swallowed exceptions
- Any "always returns True / never raises" patterns that hide real state
- IAC-specific: option-negotiation handling, terminal-type lies, fuzz opportunities if warranted

## Scope

- `tw2002_aiclient/session/iac.py` — read only
- Report written to `audit/session-iac-audit-<date>.md`

## Constraints

- **No product changes in this WO.**  Diagnose and report only.
- Bank a follow-on WO if a fix is warranted.
- Fuzz only if the test harness already supports it; do not add test infrastructure.

## Accept

1. Report exists at `audit/session-iac-audit-<date>.md`.
2. Report lists every honesty gap found (or explicitly states "none found" per category).
3. Any recommended product fix is captured as a banked follow-on WO reference (not built here).

## Proof

Read the report.  Verify `audit/session-iac-audit-<date>.md` is committed on the PR branch.
