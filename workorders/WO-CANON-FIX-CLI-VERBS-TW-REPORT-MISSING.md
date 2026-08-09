# WO-CANON-FIX-CLI-VERBS-TW-REPORT-MISSING

**Status:** DONE · docs-only · Cursor (Monk)
**Posted:** 2026-08-08

## Goal

`tw report` shipped (`WO-BUILD-POST-SESSION-ACTION-REPORT`, closed 2026-08-06) but was never given a
row in [`canon/architecture/cli-verbs.md`](../canon/architecture/cli-verbs.md)'s catalog tables — the
Implementation-status prose block already listed `report` as LIVE, but the verb had no
one-line-effect / key-args / actor-class / owning-concept row, so the catalog and the status block
disagreed on completeness even though neither disagreed on fact.
[`canon/engine/post-session-action-report.md:43-44`](../canon/engine/post-session-action-report.md)
named this exact gap: *"Not yet cataloged in CLI Verb Surface — a residual doc gap, not a missing
capability."*

## Scope

- `canon/architecture/cli-verbs.md` — add the missing `report` row.
- `canon/engine/post-session-action-report.md:43-44` — update the stale "not yet cataloged" note now
  that the gap is closed.
- No product code. Doc-completeness only.

## Verification against tip (`e554971`)

`tw2002_aiclient/session/cli.py` (`build_parser()`, `report` subparser + `cmd_report`) and a live
`tw report --help` were both read to confirm the flag set before writing the row — no flags invented:

```
usage: tw report [-h] [--ledger PATH] [--session-id ID] [--world-id SLUG]
                 [--out PATH] [--include-interrupted] [--json]
```

`report` is daemon-free (reads `state/ledger.jsonl` directly, never opens the daemon socket), never
sends a keystroke, and never gates on a decision — matching the `read-only` actor-class already used
for its closest sibling row, `log`/`trail`.

## Accept

- `cli-verbs.md`'s "Read-only introspection" table carries a `report` row with the accurate flag set
  above and links to [Post-Session Action Report](../canon/engine/post-session-action-report.md) as
  owning concept.
- `post-session-action-report.md`'s "not yet cataloged" line no longer contradicts the fix.
- No product file modified; suite count unmoved (docs-only change).

## Proof

Diff of both files below; PR + SHA in the coord log. Live-prove: n/a (docs-only, no runtime surface
touched).

## Refs

`WO-BUILD-POST-SESSION-ACTION-REPORT` (shipped, closed 2026-08-06) ·
`canon/engine/post-session-action-report.md` · `canon/architecture/cli-verbs.md` ·
`tw2002_aiclient/session/cli.py: cmd_report`
