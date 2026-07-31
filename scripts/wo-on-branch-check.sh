#!/usr/bin/env bash
# wo-on-branch-check.sh — refuse a wo/* tip that lacks matching workorders/WO-*.md
# in HEAD (WO-DEC-07-WO-ATOMIC).
#
# Coord rule (workorders-required.mdc / workorders/README.md): every hub
# HANDOFF [WO-…] must land workorders/<WO-id>.md on the hub-seeded branch in
# the same action as the coord post. This script is the mechanical gate —
# habit alone still misses.
#
# Usage:
#   scripts/wo-on-branch-check.sh                 # current branch @ HEAD
#   scripts/wo-on-branch-check.sh wo/FOO          # named branch tip
#   scripts/wo-on-branch-check.sh --ref <sha> wo/FOO
#   scripts/wo-on-branch-check.sh --help
#
# Exit: 0 WO present (or branch is not wo/*) · 1 missing WO · 2 usage/error

set -euo pipefail

usage() {
  echo "usage: $0 [--ref <commit>] [<wo-branch>]" >&2
  echo "  Default branch = current HEAD symbolic-ref; default ref = branch tip." >&2
  echo "  Non-wo/* branches exit 0 (gate applies only to hub-seeded wo/* tips)." >&2
  exit 2
}

REF=""
BRANCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      [[ $# -ge 2 ]] || usage
      REF="$2"
      shift 2
      ;;
    -h|--help) usage ;;
    -*)
      echo "unknown flag: $1" >&2
      usage
      ;;
    *)
      BRANCH="$1"
      shift
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "$BRANCH" ]]; then
  if ! BRANCH="$(git symbolic-ref -q --short HEAD 2>/dev/null)"; then
    echo "FAIL [wo-on-branch]: detached HEAD and no branch argument" >&2
    exit 2
  fi
fi

# Gate is for hub-seeded wo/<ID> tips only. Other branches are out of scope.
if [[ "$BRANCH" != wo/* ]]; then
  echo "OK [wo-on-branch]: ${BRANCH} is not wo/* — gate n/a."
  exit 0
fi

WO_ID="${BRANCH#wo/}"
if [[ -z "$WO_ID" ]]; then
  echo "FAIL [wo-on-branch]: empty WO id from branch '${BRANCH}'" >&2
  exit 2
fi

# Canonical path: workorders/WO-<id>.md (id = branch suffix after wo/).
WO_PATH="workorders/WO-${WO_ID}.md"

if [[ -z "$REF" ]]; then
  if git rev-parse -q --verify "${BRANCH}^{commit}" >/dev/null 2>&1; then
    REF="${BRANCH}"
  elif git rev-parse -q --verify "refs/heads/${BRANCH}^{commit}" >/dev/null 2>&1; then
    REF="refs/heads/${BRANCH}"
  elif git rev-parse -q --verify "refs/remotes/origin/${BRANCH}^{commit}" >/dev/null 2>&1; then
    REF="refs/remotes/origin/${BRANCH}"
  else
    echo "FAIL [wo-on-branch]: cannot resolve tip for '${BRANCH}'" >&2
    exit 2
  fi
fi

TIP="$(git rev-parse --verify "${REF}^{commit}")"

if git cat-file -e "${TIP}:${WO_PATH}" 2>/dev/null; then
  echo "OK [wo-on-branch]: ${WO_PATH} present on ${BRANCH} @ ${TIP:0:12}"
  exit 0
fi

echo "FAIL [wo-on-branch]: missing ${WO_PATH} on ${BRANCH} @ ${TIP:0:12}" >&2
echo "Hub seed ritual: commit workorders/WO-${WO_ID}.md on the branch before HANDOFF." >&2
exit 1
