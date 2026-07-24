# WO-P1-014 — World-identity rows on the launcher

> Status: DONE — hub-Accepted e73b363 (2026-07-24)
**Phase:** 1 · **Type:** extend · **Depends:** WO-P1-010
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (World identity on entry),
`canon/engine/world-identity.md`

**Goal:** Extend each launcher row with the `host` · `game_letter` · `character` columns that make
the world identity the selection is about to fix visible before the operator commits to it.

**Scope:** `tw2002_aiclient/screens.py` (launcher row layout only).

**Accept:**
- Each profile row shows its resolved `host` (or catalog display name), `game_letter`, and `handle`
  as distinct columns, matching the `name/handle/server/game/autopilot` shape
  `list_profile_summaries()` already yields per canon.
- The `game_letter` column, though narrow, is visually set off (per canon's emphasis note) rather
  than buried — bold or a distinct field, not indistinguishable filler text.
- Two profiles with the same `host`+`game_letter` but different `handle` render as visibly distinct
  rows (proves the full tuple is shown, not a collapsed subset).

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
# with two profiles sharing host+game_letter but different handle in config/profiles.toml:
.venv/bin/python -m tw2002_aiclient
# both rows visible with distinct handle text; game_letter column visually distinct per row
```
