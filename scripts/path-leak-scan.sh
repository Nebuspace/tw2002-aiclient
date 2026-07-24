#!/usr/bin/env bash
# path-leak-scan.sh — refuse operator-home absolute paths in staged (or given) content.
#
# Public-repo hygiene: committed artifacts must not contain `/Users/<username>/`
# (or `/home/<username>/`) absolute paths. Matches the intent of the Claude Code
# PreToolUse leak gate so the Cursor seat cannot silently commit what CC blocks.
#
# Usage:
#   scripts/path-leak-scan.sh              # scan `git diff --cached`
#   scripts/path-leak-scan.sh --file PATH  # scan one file
#   scripts/path-leak-scan.sh --diff -     # scan a unified diff on stdin
#
# Exit: 0 clean · 1 leak found · 2 usage/error

set -euo pipefail

PATTERN='(/Users|/home)/[A-Za-z0-9._-]+/'

usage() {
  echo "usage: $0 [--file PATH | --diff - | (default: git diff --cached)]" >&2
  exit 2
}

scan_text() {
  local label="$1"
  local text="$2"
  if printf '%s' "$text" | grep -nE "$PATTERN" >/tmp/path-leak-hits.$$ 2>/dev/null; then
    echo "FAIL [path-leak]: operator-home absolute path(s) in ${label}:" >&2
    head -20 /tmp/path-leak-hits.$$ | sed 's/^/  /' >&2
    rm -f /tmp/path-leak-hits.$$
    echo "Relativize (e.g. \"\$(git rev-parse --show-toplevel)\") before committing." >&2
    return 1
  fi
  rm -f /tmp/path-leak-hits.$$
  echo "OK [path-leak]: no /Users/<user>/ or /home/<user>/ paths in ${label}."
  return 0
}

mode="cached"
file=""
case "${1:-}" in
  "") mode="cached" ;;
  --file)
    [[ $# -eq 2 ]] || usage
    mode="file"
    file="$2"
    ;;
  --diff)
    [[ "${2:-}" == "-" ]] || usage
    mode="diff"
    ;;
  -h|--help) usage ;;
  *) usage ;;
esac

case "$mode" in
  cached)
    DIFF=$(git diff --cached 2>/dev/null || true)
    if [[ -z "$DIFF" ]]; then
      echo "INFO [path-leak]: no staged changes."
      exit 0
    fi
    scan_text "staged diff" "$DIFF"
    ;;
  file)
    [[ -f "$file" ]] || { echo "ERROR: not a file: $file" >&2; exit 2; }
    scan_text "file $file" "$(cat -- "$file")"
    ;;
  diff)
    scan_text "stdin diff" "$(cat)"
    ;;
esac
