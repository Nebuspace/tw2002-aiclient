# WO-TERMINAL-CHROME-ORPHAN-RETIRE — Retire orphaned terminal.py chrome glyph path

**Status:** OPEN · READY  
**Posted:** 2026-07-27T18:55:00Z · from `audit/session-terminal-audit-20260727.md` T-01/T-02  
**Seat:** Cursor or CC  
**Depends:** audit on main `8fae287` (#106)  
**Tip-check:** product callers of `init_locale`/`glyph_set` = **none** (audit measured) — WO still needed.

## Goal

Resolve the orphaned chrome story in `session/terminal.py`: either retire `init_locale` / `glyph_set` / `GLYPHS_*` from the session emulator and point canon at `cockpit.draw.unicode_ok`, **or** make the live TUI call one real probe (with env override) — but do **not** wire `init_locale` alone without addressing T-02 (PEP 540 utf8_mode blinds the probe under `C`).

## Accept

1. Live chrome source of truth is single and documented.
2. No leftover docs claiming `terminal.py` gates chrome unless that is true.
3. Suite green; T-02 addressed if rewiring locale probe.

## Proof

Unit + suite; live-prove n/a unless chrome visible change needs PTY.
