# WO-HUB-CLEANUP-SCRIPT-HARDEN — Fix hub-wo-merge-cleanup.sh gaps

**Status:** DONE · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28 · hub  
**Refs:** hub prune 2026-07-28 · CC PROCESS-NOTE squash reap · banked gaps after #168–#180

## Goal
Harden `scripts/hub-wo-merge-cleanup.sh` so squash-merge + GitHub auto-delete remotes do not leave worktrees or fail mid-script.

### Gaps (fix all)
1. **`origin/<branch> already absent` → early `exit 0`** currently **skips** listed/argv worktree removal. Still reap worktrees + local branch when remote is gone.
2. **`git push --delete` fails hard** when GitHub already deleted the remote (`set -e`). Treat "remote ref does not exist" as OK after worktree/local cleanup.
3. **`CLOSED` (non-merged) ≠ `MERGED`:** before deleting a CLOSED non-merged `wo/*` ref (if ever invoked), cut `preserve/<wo-id>` unconditionally (or refuse unless `--force-closed` with preserve). Do **not** treat CLOSED as MERGED via ancestry alone. Prefer `gh pr view` state.
4. Keep existing squash carve-out (`gh pr MERGED` when tip not ancestor). Document in script header comment.

### Accept
1. Script behavior matches above; small shell self-check or dry-run notes in STATUS.
2. No product/twclient changes. live-prove `n/a` (hub tooling).
3. Suite unaffected (script-only) — still run a quick sanity if CI collects nothing for scripts.

## Out of bounds
Mass-prune of live worktrees. Force-push. Changing merge ritual ownership.

## Disposition (2026-07-28T17:35Z · Cursor)

Hardened `scripts/hub-wo-merge-cleanup.sh`:

1. Remote-absent no longer `exit 0` before worktree/local reap.
2. `git push --delete` soft-fails when remote already gone.
3. CLOSED (non-merged) refused unless `--force-closed`, which cuts `preserve/<wo-id>` first.
4. Squash carve-out (`gh` MERGED) kept and documented in header.

Self-check: `bash -n` · absent branch → exit 0 reap-only · unmerged local probe → exit 2 REFUSE.
