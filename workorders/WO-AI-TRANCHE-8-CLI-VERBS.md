# WO-AI-TRANCHE-8-CLI-VERBS

**Status:** DONE (docs batch)
**Branch:** `wo/AI-TRANCHE-8-CLI-VERBS`
**Gated:** no (docs-only)

## Goal

Close the last residual doc-vs-live flag mismatch left over from
`WO-ESCALATE-CLI-VERBS-DOC-VS-LIVE-MISMATCH` (Option B) — no code behavior
changes.

## Scope

`canon/architecture/cli-verbs.md`:

1. `analyze <session>` TARGET row (Teach table) — key args still cited
   `--min-support --top`; `mine_cli.py`'s shipped flag (which `analyze` was
   modeled on) is `--top-k`. Corrected to `--min-support --top-k`.
2. Examples block — `# tw analyze all --top 10` corrected to
   `# tw analyze all --top-k 10`.
3. Same examples block incorrectly filed `tw mine --min-support 3` under
   "TARGET (not runnable today)" even though the Teach table two rows above
   (and the Implementation-status HOLD-list carve-out) already say `mine` is
   **LIVE**. Moved the example line to the "LIVE today" half and dropped the
   stale "ledger mining ... stay engine-or-script paths" framing sentence
   that no longer matches `mine`'s shipped state.

## Verify-first (tip-check against origin/main)

- `origin/main` tip at check time: `7c97b2a` (`canon/architecture/cli-verbs.md`
  last touched by `2cf7e8a`, the WO-AI-TRANCHE-6 players-LIVE revert).
- Confirmed live via `tw2002_aiclient/session/cli.py` `build_parser()`
  (imported in a throwaway venv): `mine`/`patterns` registered by
  `mine_cli.add_mine_parsers` with `--top-k` (not `--top`); no top-level
  `analyze` subparser exists (`teach_cli.add_teach_parser` registers
  `teach analyze`, a differently-shaped verb — out of scope for this pass,
  flagged as a Concern in the return report, not fixed here).
- `haggle`/`autopilot`/`autoloop`/`replay`/`play`/`crawl` HOLD rows and the
  Implementation-status HOLD list were re-checked against tip and are still
  accurate — no further edits needed there this pass.

## Accept

Both residual `--top` flag mismatches corrected; `tw mine` no longer
misfiled as not-runnable in the same doc that calls it LIVE two sections
earlier; path-leak scan clean; PR ready for review.

## Proof

`scripts/path-leak-scan.sh` on staged paths; diff review only (docs-only,
no product suite required). `live-prove: n/a` (docs-only, matches parent
WO-ESCALATE-CLI-VERBS-DOC-VS-LIVE-MISMATCH's own `live-prove: n/a`).
