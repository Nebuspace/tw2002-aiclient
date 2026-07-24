# WO-P1-017 — Launcher color/glyph polish

> Status: DONE — hub-Accepted aadf2aa (2026-07-24)
**Phase:** 1 · **Type:** polish · **Depends:** WO-P1-010, WO-P1-011
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (Visual design & polish, Color semantics
for the launcher), `canon/surfaces/visual-language.md`

**Goal:** Apply the shared visual-language palette's calm end to the launcher — cyan chrome, muted
steady-state rows, a warn-tinted broken-profile row, and reverse-video selection — replacing the
plain-text CLI-era rendering with the consolidated picker's aspirational styling.

**Scope:** `tw2002_aiclient/screens.py` (launcher color-pair application only) — must reuse the
shared `_SEMANTIC_COLORS` 7-tone table and the single `A_REVERSE` selection convention; no new local
color scheme.

**Accept:**
- Box chrome (borders, titles) renders `info` (cyan) — never used for row data, matching the
  "cyan is chrome, never data" rule.
- A broken-profile row (from WO-P1-011) renders `warn` (yellow), visually distinct from a healthy
  `muted` row.
- A row whose `autopilot` flag is set renders `ok` (green) — a capability flag shown, not an armed
  run (arming still happens confirm-gated in the cockpit, unaffected by this WO).
- The currently-selected row is drawn `A_REVERSE`, and no other selection convention is introduced.
- ASCII-fallback terminals (unicode_ok=False) degrade the same box-drawing weight without losing
  which row is broken/armed/selected.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient
# visually confirm: cyan chrome, warn row on the broken-profile fixture, ok row on autopilot=true,
# reverse-video on the selected row; toggle TERM=vt100-ish / force ASCII glyphs and re-confirm parity
```
