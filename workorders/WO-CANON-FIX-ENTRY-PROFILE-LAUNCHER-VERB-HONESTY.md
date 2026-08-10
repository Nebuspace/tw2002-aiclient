# WO-CANON-FIX-ENTRY-PROFILE-LAUNCHER-VERB-HONESTY

**Goal:** Tip-true `canon/surfaces/entry-and-profile-selection.md` launcher/rotation
verb claims that contradict tip `build_parser()` / product entry and sibling
`cli-verbs.md`.

**Depends-on:** tip `origin/main` after #670 (`a17994f3`); `cli-verbs.md` already
honest that `aiclient` is **not** a `tw` subcommand and that `players` is
`{list,next,rotate}` only.

**Scope:**
- `canon/surfaces/entry-and-profile-selection.md` — rotation touchpoint prose,
  visual-design "composed CLI verbs" list, Code divergence launcher bullet,
  Citations code-module list.
- `workorders/WO-CANON-FIX-ENTRY-PROFILE-LAUNCHER-VERB-HONESTY.md` — this file.

**Constraints:**
- Docs-only. Do **not** invent `tw players add` or `tw aiclient` / `cmd_aiclient`.
- Do not expand TARGET vocabulary; align prose to tip truth already catalogued in
  `cli-verbs.md`.
- Skip Max-gated `WO-ESCALATE-BOUNDED-REPEAT-*`.

**Accept:**
- No `tw aiclient` / `cmd_aiclient` claims; product entry named as
  `./tw2002-aiclient` / `python -m tw2002_aiclient` (`app.py` / `__main__.py`).
- No `tw players add` / `cmd_players_add` claims; LIVE bank verbs are
  `list` / `next` / `rotate` via `players_cli.py`.
- Citations point at real modules (`catalog_cli.py`, `players_cli.py`) — not a
  fictional `cli.py` home for those cmds.
- Code divergence still records "launcher is CLI-composed, not one curses screen"
  without naming phantom verbs.

**Proof:** `rg` on the concept for `tw aiclient|cmd_aiclient|players add|cmd_players_add`
→ empty (except this WO's Accept text if cited); cross-check
`players_cli.py` / `cli-verbs.md` players row; docs-only → live-prove n/a.

**Refs:** `canon/architecture/cli-verbs.md` (`aiclient` Not-a-subcommand row;
`players {list,next,rotate}`); `tw2002_aiclient/players_cli.py`;
`tw2002_aiclient/catalog_cli.py`; `tw2002_aiclient/__main__.py` /
`./tw2002-aiclient`; tip `origin/main@a17994f3` (#670).
