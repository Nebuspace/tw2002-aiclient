# WO-BUILD-CONSOLIDATED-LAUNCHER-SURFACE

**Status:** tip-check reframed — product surface LIVE; deliverable is canon honesty  
**Branch:** `wo/BUILD-CONSOLIDATED-LAUNCHER-SURFACE`  
**Seat:** impl-aiclient-h1

## Goal

Close the READY-row premise that the entry surface is still CLI-only with no consolidated curses picker. Tip already ships `LauncherScreen` + `CreateFormScreen` + `BankViewScreen` via `./tw2002-aiclient` / `python -m tw2002_aiclient`. Canon (`entry-and-profile-selection.md`) still narrates that picker as unbuilt TARGET — that is doc drift, not a missing UI.

## Scope

- `canon/surfaces/entry-and-profile-selection.md` — rewrite Code divergence + Visual design framing so tip-true LIVE curses launcher is named; keep CLI verbs as companion surfaces; keep `[ASPIRATIONAL]` only for polish not yet on tip.
- This workorder file.

## Out of scope

- New TUI chrome / glyph / color ASPIRATIONAL polish.
- Adding a `tw aiclient` subcommand (cli-verbs already correctly says product is `./tw2002-aiclient`).
- Auth / secrets / live-drive changes.

## Accept

- Code divergence no longer claims the consolidated visual picker is unbuilt.
- Visual design intro no longer says "the entry surface is not a curses screen at all."
- LIVE modules named with tip path evidence (`screens.LauncherScreen`, `create_form_screen.CreateFormScreen`, `BankViewScreen`, `app.py` entry).
- CLI companion verbs (`tw players *`, `tw servers list`) still documented as live companions, not deleted.

## Proof

- Docs-only → live-prove `n/a`.
- `rg -n 'not a curses screen|unbuilt picker|still TARGET' canon/surfaces/entry-and-profile-selection.md` returns no stale "unbuilt" claims for the consolidated picker itself.
