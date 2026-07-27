#!/usr/bin/env bash
# hub-wo-merge-cleanup.sh — After a hub-merged WO PR, delete the wo/<ID> branch
# and remove any local worktree still pointing at it.
#
# ORCHESTRATOR-ONLY. Part of the merge ritual (see workorders/WO-PR-CI-LIVE-PROVE-SPLIT.md
# § Hub merge ritual, and .cursor/rules/workorders-required.mdc).
#
# Usage:
#   ./scripts/hub-wo-merge-cleanup.sh <wo-branch> [worktree-path ...]
#
#   # Typical after PR merge:
#   ./scripts/hub-wo-merge-cleanup.sh wo/PR-CI-LIVE-PROVE-SPLIT /private/tmp/tw2002-hub-pr-ci
#
# Preconditions:
#   - The PR for this branch is already MERGED (script refuses if the branch tip
#     is not an ancestor of origin/main).
#   - You are not currently checked out on that branch in the primary tree.
#
# What it does:
#   1. Verifies origin/main contains the branch tip (merged).
#   2. Removes any listed worktrees (or auto-discovers worktrees on that branch).
#   3. Deletes origin/<branch> and the local branch ref.
#   4. Fetches --prune.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="${1:-}"

if [[ -z "$BRANCH" ]]; then
  echo "Usage: $0 <wo-branch> [worktree-path ...]"
  echo "  Example: $0 wo/TUI-DEAD-TERMINAL-SPIN /private/tmp/tw2002-wo-tui"
  exit 1
fi
shift || true

cd "$REPO_ROOT"
git fetch origin main --quiet

if ! git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
  echo "OK: origin/${BRANCH} already absent (nothing to delete)."
  exit 0
fi

TIP="$(git rev-parse "origin/${BRANCH}")"
if git merge-base --is-ancestor "$TIP" origin/main; then
  : # merge-commit workflow — tip reachable from main
elif command -v gh >/dev/null 2>&1 \
  && [[ -n "$(gh pr list --head "$BRANCH" --state merged --json number -q '.[0].number' 2>/dev/null || true)" ]]; then
  # Squash-merge carve-out (WO-LIFECYCLE-SQUASH-ON-ORIGIN): pre-squash tips are
  # never ancestors of main after squash. A MERGED PR with this head is enough.
  echo "OK: origin/${BRANCH} tip ${TIP:0:7} not an ancestor of main, but gh reports a MERGED PR for this head (squash-safe)."
else
  echo "REFUSE: origin/${BRANCH} tip ${TIP:0:7} is NOT an ancestor of origin/main,"
  echo "        and no MERGED PR was found for head=${BRANCH}."
  echo "        For squash repos, prefer: gh pr view <n> state=MERGED + per-path blob identity"
  echo "        (see workorders/WO-LIFECYCLE-SQUASH-ON-ORIGIN.md). No delete performed."
  exit 2
fi

remove_wt() {
  local wt="$1"
  [[ -z "$wt" ]] && return 0
  if [[ -d "$wt" ]]; then
    echo "Removing worktree: $wt"
    git worktree remove --force "$wt"
  fi
}

# Explicit paths from argv
for wt in "$@"; do
  remove_wt "$wt"
done

# Auto-discover remaining worktrees checked out on this branch
current_path=""
current_branch=""
while IFS= read -r line; do
  case "$line" in
    worktree\ *)
      current_path="${line#worktree }"
      current_branch=""
      ;;
    branch\ *)
      current_branch="${line#branch refs/heads/}"
      if [[ "$current_branch" == "$BRANCH" ]]; then
        remove_wt "$current_path"
      fi
      ;;
    "")
      current_path=""
      current_branch=""
      ;;
  esac
done < <(git worktree list --porcelain)

echo "Deleting origin/${BRANCH} (tip ${TIP:0:7} ⊂ origin/main)"
git push origin --delete "$BRANCH"
git branch -D "$BRANCH" 2>/dev/null || true
git fetch --prune origin --quiet

echo "Done — ${BRANCH} cleaned up."
