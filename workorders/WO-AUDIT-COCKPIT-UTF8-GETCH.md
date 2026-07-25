# WO-AUDIT-COCKPIT-UTF8-GETCH — refuse multi-byte UTF-8 getch bursts

> Status: **REVISE** 2026-07-25 · seat `impl-aiclient-cursor` · hub-ruled `@ 14:11:28Z` · REVISE `@ 15:19:39Z`  
> Phase: audit / cockpit honesty · Type: harden  
> Refs: F9 pty proof · hub UTF-8 contract (not literal cli latin-1 mirror)

## Goal

One physical UTF-8 keypress must not become N forwarded game bytes.

## Accept

1. Multi-byte getch sequence (lead `0xC0`–`0xF4` + continuations) → **refuse + tell** on status line · **zero** bytes forwarded · session stays alive
2. Notice pure ASCII naming `U+XXXX` — never a glyph
3. Bare single-byte `0x80`–`0xFF` still forwards (deliberate divergence from naive cli mirror)
4. `key >= 256` path untouched · no silent-drop `else:` rewrite
5. Suite green · red-first inject proof
6. **REVISE:** incomplete lead + non-continuation next key → `ungetch` so the next keystroke still reaches the game (must not silent-swallow)

## Scope

`tw2002_aiclient/app.py` attach key path + `tests/test_cockpit_utf8_getch.py`

## Out

`cli.py` · daemon · menu crawler
