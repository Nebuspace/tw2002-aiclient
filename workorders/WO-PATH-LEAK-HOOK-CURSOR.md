# WO-PATH-LEAK-HOOK-CURSOR — Cursor path-leak gate: pre-commit hook for absolute-path leak

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`c9b648d`** (Cursor)
> Type: process/tooling · Phase: 0 · Seat: impl-aiclient-cursor
> Refs: `.git/hooks/pre-commit` or CI hook · `WO-P0-STATUS-TRUTH.md` (parallel)

## Goal
Gate absolute-path leaks in committed files for the Cursor seat. Add or wire a pre-commit hook (or CI check) that detects absolute paths (e.g., paths under the operator home) before they land in workorder Proof commands, canon, or docs. Closes the risk surfaced by `WO-PATH-RELATIVIZE`.

## Scope
- `.git/hooks/pre-commit` (or equivalent hook/CI) — absolute-path scan

## Accept
- Hook fires on an injected absolute path in a test commit
- Hook passes when all paths are relative
- SHA `c9b648d`

## Refs
Cursor STATUS @ impl-aiclient-cursor:512 · SHA `c9b648d` · parallel with `WO-P0-STATUS-TRUTH` (item B in same HANDOFF bundle)
