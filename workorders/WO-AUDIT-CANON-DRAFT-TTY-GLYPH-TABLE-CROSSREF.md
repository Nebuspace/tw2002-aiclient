# WO-AUDIT-CANON-DRAFT-TTY-GLYPH-TABLE-CROSSREF

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** LOW
**Depends-on:** none (CLI-ASCII-WRITE-CHOKE product WO remains BANKED/STAGED separately)
**Gated:** no — docs cross-ref only

## Goal

Write DECISIONS §B ↔ tip `session/tty_encode.py` cross-reference so the substitute
table / fail-loud contract is discoverable from canon, not only a code comment.

## Scope

- `canon/DECISIONS.md` §B
- This WO file

## Accept

1. §B names `tty_encode.substitute_for_tty` / `encode_for_tty` and fail-loud rule.
2. Notes CLI-ASCII-WRITE-CHOKE remains a separate product bank (not closed by this doc).
3. live-prove: `n/a` (docs-only).

## Proof

`rg tty_encode|substitute_for_tty canon/DECISIONS.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-TTY-GLYPH-TABLE-CROSSREF`
- `tw2002_aiclient/session/tty_encode.py`
- findings.md `CLI-ASCII-WRITE-CHOKE`
