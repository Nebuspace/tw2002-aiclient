#!/usr/bin/env bash
# hub-wo-merge-cleanup.sh — After a hub-merged WO PR, delete the wo/<ID> branch
# and remove any local worktree still pointing at it.
#
# ORCHESTRATOR-ONLY. Part of the merge ritual (see workorders/WO-PR-CI-LIVE-PROVE-SPLIT.md
# § Hub merge ritual, and .cursor/rules/workorders-required.mdc).
#
# Usage:
#   ./scripts/hub-wo-merge-cleanup.sh <wo-branch> [worktree-path ...]
#   ./scripts/hub-wo-merge-cleanup.sh --force-closed <wo-branch> [worktree-path ...]
#
#   # Typical after PR merge:
#   ./scripts/hub-wo-merge-cleanup.sh wo/PR-CI-LIVE-PROVE-SPLIT /private/tmp/tw2002-hub-pr-ci
#
# Landed signal (do NOT use ancestry alone for squash repos):
#   - merge-commit workflow: tip is an ancestor of origin/main, OR
#   - squash carve-out: `gh pr list --head <branch> --state merged` reports a PR
#     (pre-squash tip is never an ancestor of main after squash).
#   CLOSED ≠ MERGED. A CLOSED non-merged branch is refused unless --force-closed,
#   which first cuts preserve/<wo-id> from the tip (failure-to-keep > failure-to-clean).
#
# Gaps closed (WO-HUB-CLEANUP-SCRIPT-HARDEN):
#   1. origin/<branch> already absent → still reap worktrees + local branch (no early exit).
#   2. git push --delete soft-fails when GitHub already deleted the remote.
#   3. CLOSED non-merged → preserve/<wo-id> before any delete (--force-closed only).
#
# What it does:
#   1. Fetches origin/main; resolves tip from origin/<branch> or local <branch>.
#   2. Gates on MERGED (ancestor or gh) — or preserve+force for CLOSED.
#   3. Removes listed / auto-discovered worktrees on that branch.
#   4. Soft-deletes origin/<branch>; deletes local branch; fetch --prune.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORCE_CLOSED=0
BRANCH=""

usage() {
  echo "Usage: $0 [--force-closed] <wo-branch> [worktree-path ...]"
  echo "  Example: $0 wo/TUI-DEAD-TERMINAL-SPIN /private/tmp/tw2002-wo-tui"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-closed) FORCE_CLOSED=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "Unknown flag: $1"
      usage
      exit 1
      ;;
    *)
      BRANCH="$1"
      shift
      break
      ;;
  esac
done

if [[ -z "$BRANCH" ]]; then
  usage
  exit 1
fi

# Remaining argv = optional worktree paths
WT_ARGS=("$@")

cd "$REPO_ROOT"
git fetch origin main --quiet

wo_id_from_branch() {
  # wo/FOO → FOO ; bare FOO → FOO
  local b="$1"
  if [[ "$b" == wo/* ]]; then
    echo "${b#wo/}"
  else
    echo "$b"
  fi
}

gh_pr_state() {
  # Prints MERGED | CLOSED | OPEN | NONE
  if ! command -v gh >/dev/null 2>&1; then
    echo "NONE"
    return 0
  fi
  local merged closed
  merged="$(gh pr list --head "$BRANCH" --state merged --json number -q '.[0].number' 2>/dev/null || true)"
  if [[ -n "$merged" ]]; then
    echo "MERGED"
    return 0
  fi
  closed="$(gh pr list --head "$BRANCH" --state closed --json number,mergedAt -q '.[0] | select(.mergedAt == null) | .number' 2>/dev/null || true)"
  if [[ -n "$closed" ]]; then
    echo "CLOSED"
    return 0
  fi
  local open
  open="$(gh pr list --head "$BRANCH" --state open --json number -q '.[0].number' 2>/dev/null || true)"
  if [[ -n "$open" ]]; then
    echo "OPEN"
    return 0
  fi
  echo "NONE"
}

# Hub may ONLY reap hub-owned worktrees (allowlist). Everything else REFUSE/SKIP.
# Incidents 2026-07-28: auto-discover reaped seat cc-* lanes twice after merge.
# Blocklist of seat names is the weak half — allowlist inverts the failure mode.
is_hub_owned_wt() {
  local wt="$1"
  local base
  base="$(basename "$wt")"
  [[ "$base" == hub-* ]] && return 0
  [[ "$wt" == */.worktrees/hub-* ]] && return 0
  [[ "$wt" == /private/tmp/hub-* ]] && return 0
  [[ "$wt" == /tmp/hub-* ]] && return 0
  return 1
}

remove_wt() {
  local wt="$1"
  local mode="${2:-auto}" # auto | explicit
  [[ -z "$wt" ]] && return 0
  if ! is_hub_owned_wt "$wt"; then
    if [[ "$mode" == "explicit" ]]; then
      # Caller must pre-validate; this path is a last-resort guard.
      echo "REFUSE: $wt is not hub-owned (need basename hub-* under .worktrees/ or /private/tmp/hub-*). Owning seat reaps." >&2
      exit 2
    fi
    echo "SKIP non-hub worktree (auto-discover): $wt"
    return 0
  fi
  if [[ -d "$wt" ]]; then
    echo "Removing worktree: $wt"
    git worktree remove --force "$wt"
  fi
}

reap_worktrees() {
  local wt
  # All-or-nothing: validate every explicit argv BEFORE any remove, so a mixed
  # list cannot leave half the hubs reaped under a REFUSE exit code (CC 21:08:44Z).
  for wt in "${WT_ARGS[@]+"${WT_ARGS[@]}"}"; do
    [[ -z "$wt" ]] && continue
    if ! is_hub_owned_wt "$wt"; then
      echo "REFUSE: $wt is not hub-owned (need basename hub-* under .worktrees/ or /private/tmp/hub-*). Owning seat reaps." >&2
      echo "REFUSE: aborting before any worktree remove (all-or-nothing argv gate)." >&2
      exit 2
    fi
  done
  for wt in "${WT_ARGS[@]+"${WT_ARGS[@]}"}"; do
    remove_wt "$wt" explicit
  done

  local current_path="" current_branch=""
  while IFS= read -r line; do
    case "$line" in
      worktree\ *)
        current_path="${line#worktree }"
        current_branch=""
        ;;
      branch\ *)
        current_branch="${line#branch refs/heads/}"
        if [[ "$current_branch" == "$BRANCH" ]]; then
          remove_wt "$current_path" auto
        fi
        ;;
      "")
        current_path=""
        current_branch=""
        ;;
    esac
  done < <(git worktree list --porcelain)
}

soft_delete_remote() {
  # Gap 2: GitHub often auto-deletes the remote after merge — never abort cleanup.
  if ! git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
    echo "OK: origin/${BRANCH} already absent (skip push --delete)."
    return 0
  fi
  echo "Deleting origin/${BRANCH} (tip ${TIP:0:7})"
  if git push origin --delete "$BRANCH"; then
    return 0
  fi
  echo "OK: push --delete failed (remote likely already gone) — continuing local cleanup."
  return 0
}

delete_local_branch() {
  if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    git branch -D "$BRANCH" 2>/dev/null || true
  fi
}

# Resolve tip: prefer origin, else local (remote may already be gone — gap 1).
REMOTE_PRESENT=0
TIP=""
if git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
  REMOTE_PRESENT=1
  TIP="$(git rev-parse "origin/${BRANCH}")"
elif git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  TIP="$(git rev-parse "refs/heads/${BRANCH}")"
  echo "NOTE: origin/${BRANCH} absent; using local tip ${TIP:0:7}."
else
  # Nothing left except maybe orphaned worktrees still listing the branch name.
  echo "OK: no origin/${BRANCH} and no local ${BRANCH} — reaping any leftover worktrees only."
  reap_worktrees
  git fetch --prune origin --quiet
  echo "Done — ${BRANCH} already gone."
  exit 0
fi

PR_STATE="$(gh_pr_state)"
echo "PR state for head=${BRANCH}: ${PR_STATE}"

LANDING_OK=0
if git merge-base --is-ancestor "$TIP" origin/main; then
  LANDING_OK=1
  echo "OK: tip ${TIP:0:7} is an ancestor of origin/main."
elif [[ "$PR_STATE" == "MERGED" ]]; then
  LANDING_OK=1
  echo "OK: tip ${TIP:0:7} not an ancestor of main, but gh reports MERGED (squash carve-out)."
fi

if [[ "$LANDING_OK" -eq 1 ]]; then
  :
elif [[ "$PR_STATE" == "CLOSED" ]]; then
  # Gap 3: CLOSED ≠ MERGED — preserve before any delete.
  if [[ "$FORCE_CLOSED" -ne 1 ]]; then
    echo "REFUSE: PR for head=${BRANCH} is CLOSED (not merged)."
    echo "        Cut preserve/$(wo_id_from_branch "$BRANCH") and re-run with --force-closed,"
    echo "        or leave the branch alone. Ancestry alone must not authorize this delete."
    exit 2
  fi
  WO_ID="$(wo_id_from_branch "$BRANCH")"
  PRESERVE_REF="preserve/${WO_ID}"
  if git show-ref --verify --quiet "refs/heads/${PRESERVE_REF}"; then
    echo "OK: ${PRESERVE_REF} already exists."
  else
    echo "Preserving tip ${TIP:0:7} as ${PRESERVE_REF} before CLOSED cleanup."
    git branch "$PRESERVE_REF" "$TIP"
  fi
elif [[ "$PR_STATE" == "OPEN" ]]; then
  echo "REFUSE: PR for head=${BRANCH} is still OPEN. Merge (or close+--force-closed) first."
  exit 2
else
  echo "REFUSE: tip ${TIP:0:7} is NOT an ancestor of origin/main,"
  echo "        and no MERGED PR was found for head=${BRANCH} (gh state=${PR_STATE})."
  echo "        For squash repos, prefer: gh pr view <n> state=MERGED."
  echo "        No delete performed."
  exit 2
fi

# Worktrees first (gap 1: must run even when remote already gone).
reap_worktrees

soft_delete_remote
delete_local_branch
git fetch --prune origin --quiet

echo "Done — ${BRANCH} cleaned up."
