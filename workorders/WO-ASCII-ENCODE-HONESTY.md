# WO-ASCII-ENCODE-HONESTY

**Status:** OPEN · Claude Code preferred  
**Posted:** 2026-07-26 (Max carte blanche §B)

## Goal

Under `LC_ALL=C` / ASCII output paths: **no silent content holes**. Non-encodable glyphs use the documented substitute table or a controlled loud failure — never a successful-looking send that dropped characters.

## Scope

- Encode / write paths that hit the operator TTY or telnet send under ASCII mode
- Pins proving substitute-or-loud (em-dash and kin)

## Constraints

- Align `DECISIONS.md` §B · do not expand secrets gate
- Prefer substitute table already used for box-drawing where TW-safe

## Accept

Silent-drop impossible on covered paths; pins red→green; STATUS.

## Proof

Targeted pytest + STATUS + SHA.

## Refs

Max carte blanche 2026-07-26 §B · prior ASCII audit WOs
