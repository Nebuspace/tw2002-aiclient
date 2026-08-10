# WO-CANON-FIX-ENTRY-PROFILE-BODY-CLI-CITATION

**Goal:** Tip-true body sections in `canon/surfaces/entry-and-profile-selection.md`
that #671 left behind — Citations/Code-divergence already named `catalog_cli` /
`players_cli`, but new-player flow + Spacing still cited phantom `cli.py` homes,
`servers.list_servers()` / `servers.resolve_endpoint()`, and retired KEY/HOST/PORT
column layouts.

**Depends-on:** tip `origin/main` after #671 (`f465924b`).

**Scope:**
- `canon/surfaces/entry-and-profile-selection.md` — new-player flow, Spacing /
  alignment, one Code-divergence dual-directory bullet, Citations config paths.
- `workorders/WO-CANON-FIX-ENTRY-PROFILE-BODY-CLI-CITATION.md` — this file.

**Constraints:**
- Docs-only. Do not invent a `servers.resolve_endpoint()` helper or revive the
  retired fixed-width `tw servers list` KEY/HOST/PORT layout.
- Keep the dual-directory split honest: `servers.toml` = profile binding;
  `servers.inventory.json` = research/`tw servers list` / `tw probe`.
- Skip Max-gated `WO-ESCALATE-BOUNDED-REPEAT-*`.

**Accept:**
- New-player flow does not claim `tw servers list` = `cli.py::cmd_servers_list →
  servers.list_servers()` over `servers.toml`.
- Spacing cites `catalog_cli` / `players_cli` tip formats (summary report +
  players columnar + probe OPEN/FAIL tabs) — no `cli.py:NNN` line cites.
- Code divergence records the dual-directory split; Citations name both
  `servers.toml` and `servers.inventory.json`.

**Proof:** `rg` concept for `cli.py::cmd_servers_list|servers\.list_servers\(\)|cli\.py:\d+`
→ only intentional "retired / no longer" prose; cross-check
`catalog_cli.format_servers_report` + `players_cli.cmd_players_list`; docs-only →
live-prove n/a.

**Refs:** PR #671 (launcher verb honesty — Citations half); `tw2002_aiclient/catalog_cli.py`;
`tw2002_aiclient/server_inventory.py`; `tw2002_aiclient/players_cli.py`;
`tw2002_aiclient/session/credentials.py` (`list_servers` / `create_profile`);
tip `origin/main@f465924b`.
