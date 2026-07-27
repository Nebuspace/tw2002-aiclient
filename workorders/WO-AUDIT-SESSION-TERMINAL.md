# WO-AUDIT-SESSION-TERMINAL — Honesty audit of session/terminal.py (encoding/glyph/locale)

**Status:** DONE · Cursor
**Posted:** 2026-07-26
**Seat:** Cursor (`impl-aiclient-cursor`)
**Done:** 2026-07-27 · report `audit/session-terminal-audit-20260727.md` (code tip audited `f96d68b`)

## Goal

READ-ONLY honesty audit of `tw2002_aiclient/session/terminal.py` with focus on:

- Encoding / decoding contracts: what codec is claimed vs what is actually applied
- Glyph / control-character handling: documented vs actual behaviour on non-ASCII input
- Locale / LANG assumptions: any implicit UTF-8 that can break on a bare ASCII locale
- Unicode-ok assertions: any `unicode_ok` or similar flags that may be set incorrectly
- Silent lossy paths: `errors='replace'` / `errors='ignore'` without documentation

## Scope

- `tw2002_aiclient/session/terminal.py` — read only
- Report written to `audit/session-terminal-audit-<date>.md`

## Constraints

- **No product changes in this WO.**  Diagnose and report only.
- Bank a follow-on WO if a fix is warranted.
- Do not add test infrastructure.

## Accept

1. Report exists at `audit/session-terminal-audit-<date>.md`.
2. Report covers each category (encoding, glyph, locale, unicode-ok, silent-lossy) with explicit
   "none found" where clean.
3. Any fix is banked as a follow-on WO reference, not built here.

## Proof

Read the report.  Verify `audit/session-terminal-audit-<date>.md` is committed on the PR branch.
