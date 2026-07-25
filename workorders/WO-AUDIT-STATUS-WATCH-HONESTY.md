# WO-AUDIT-STATUS-WATCH-HONESTY — F7+F8 status/watch prompt-echo + tx-record honesty

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **HANDOFF'd** 2026-07-25 · dispatched to Cursor in wave @ 13:29:19Z (F7+F8 · product · build in worktree, push behind Lane C)
> Type: harden · Priority: P1 · Lens: L2 code-vs-canon / honesty
> Refs: `canon/architecture/secrets-and-credentials.md` prompt-echo DOC-GAP · `canon/engine/trace-ledger.md`

## Goal
F7: `status` verb prompt-echo honesty — ensure the `status` command does not accidentally echo a prompt that looks like a secret. F8: `tx record` (or equivalent) honesty — TX record path does not embed raw credentials or session secrets in returned data structures.

## Scope (product · build in worktree, push behind Lane C)
- `tw2002_aiclient/session/cli.py` / protocol layer — status/watch prompt-echo probe
- TX record path — secret exclusion verify
- `tests/` — probe assertions

## Constraints
- Build in isolated worktree; push behind Lane C (cli.py owner)
- No `git stash`
- Full suite green; path-leak

## Accept
1. Status verb does not echo a prompt that looks like a secret
2. TX record path does not embed raw credentials
3. Tests green

## Proof
STATUS + SHA with probe evidence; Push waits Accept + Lane-C-clear.

## Refs
hub HANDOFF wave @ 13:29:19Z (F7+F8) · `secrets-and-credentials.md` prompt-echo DOC-GAP · `trace-ledger.md`
