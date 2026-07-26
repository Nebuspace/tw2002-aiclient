# WO-DOCS-INTO-CANON

**Status:** DONE · origin `3733d9c`  
**Posted:** 2026-07-25T21:03:14Z

## Goal

Eliminate `docs/` by folding its content into `canon/` OKF; update all in-repo pointers; delete the directory.

## Scope

Throwaway worktree off `origin/main`:

- Fold `docs/OPERATOR.md` into OKF — prefer extending `canon/surfaces/entry-and-profile-selection.md` + `canon/architecture/cli-verbs.md` / session cold-start concepts; if a dedicated concept is cleaner, add `canon/surfaces/operator-cold-start.md` (OKF frontmatter) and index it in `canon/index.md`.
- Fold `docs/community-sources.md` into `canon/doctrine/server-catalog-sources.md` (OKF frontmatter) + index entry — catalog provenance / community links / honesty policy.
- Delete `docs/` entirely once folded.
- Update pointers: `README.md`, `research/README.md`, `canon/findings.md`, `workorders/WO-SERVERS-CATALOG-*.md`, any other `docs/` refs (`rg docs/`).
- Stamp `canon/DECISIONS.md` Accepted ruling already hub-appended — verify it landed; do not duplicate conflicting Pending.

## Constraints

- No product `.py` behavior change.
- Stay off CC lanes (`cli.py` / login / classify parked tip).
- No secrets; public-OK only.
- Prefer **fold+trim** over paste-duplicating README.

## Accept

- `docs/` gone.
- Content reachable from `canon/index.md`.
- `rg 'docs/'` clean of live pointers (historical workorder Status prose may note migration).
- README points at canon only.

## Proof

STATUS + SHA; list new/updated canon paths.

## Refs

- Max @ 2026-07-25T21:03:14Z — no `docs/` · fold into OKF
- CLAUDE.md sole-docs-root
- Prior HEADS-UP docs/ conflict
