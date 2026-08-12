# WO-CANON-FIX-DEV-DRIVE-EXCEPTION-LINE-DRIFT

**Goal:** refresh `canon/doctrine/dev-drive-exception.md`'s stale `protocol.py`
line citations for the hardcoded `sender="app"` gate.

**Depends-on:** tip `origin/main` at `4bde1dc7` (post #674).

**Scope:**
- `canon/doctrine/dev-drive-exception.md` — residual-path line citations only.
- `workorders/WO-CANON-FIX-DEV-DRIVE-EXCEPTION-LINE-DRIFT.md` — this file.

**Constraints:**
- Docs-only. LOW, ungated, no schema/migration.
- Substance claim stays: `tw do` / `tw send` never reach the `dev`-sender gate;
  only line numbers move.
- Do not invent a CLI `--sender dev` surface here (that remains
  `WO-WIRE-DEV-SENDER-CLI-PATH`).

**Accept:**
- Citations point at the actual current `sender="app"` send sites
  (`protocol.py:1493`, `:1535`) plus the login-default note (`:1985`).
- `_record_ledger` cite matches tip (`:1300`, was `:1264`).
- Doc's substance claim (`tw do`/`tw send` never reach the dev-sender gate)
  stays correct.

**Proof:** docs-only; live-prove `n/a` (cannot touch live).

**Refs:** hub HANDOFF `2026-08-12T00:28:52Z` · `queue-aiclient.md:832` ·
verify-first re-grep on tip `4bde1dc7`.
