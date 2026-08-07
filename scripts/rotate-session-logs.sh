#!/usr/bin/env bash
# rotate-session-logs.sh — local hygiene for project-rooted logs/session-*.log
#
# Session transcripts are created at daemon start (TranscriptLogger) even when
# the session dies before any RX/TX — that yields empty 0-byte files. logs/ is
# gitignored (.gitignore:3); this script never stages or commits anything.
#
# Usage (from repo root or any cwd — resolves LOG_DIR from env or ./logs):
#   scripts/rotate-session-logs.sh              # delete 0-byte session-*.log
#   scripts/rotate-session-logs.sh --days 30    # also delete session-*.log mtime >30d
#   scripts/rotate-session-logs.sh --dry-run    # print actions only
#
# Exit: 0 ok · 1 usage/error · never touches paths outside the chosen log dir.

set -euo pipefail

DRY_RUN=0
DAYS=""
LOG_DIR="${TW2002_LOG_DIR:-}"

usage() {
  echo "usage: $0 [--dry-run] [--days N] [--log-dir DIR]" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --days)
      [[ $# -ge 2 ]] || usage
      DAYS="$2"
      [[ "$DAYS" =~ ^[0-9]+$ ]] || usage
      shift 2
      ;;
    --log-dir)
      [[ $# -ge 2 ]] || usage
      LOG_DIR="$2"
      shift 2
      ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

if [[ -z "$LOG_DIR" ]]; then
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  LOG_DIR="${ROOT}/logs"
fi

if [[ ! -d "$LOG_DIR" ]]; then
  echo "OK [rotate-logs]: no log dir at ${LOG_DIR} — nothing to do."
  exit 0
fi

# Resolve to absolute for safety messaging; never follow symlinks out.
LOG_DIR="$(cd "$LOG_DIR" && pwd)"

removed=0
skipped=0

remove_one() {
  local f="$1"
  local reason="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN would remove (${reason}): ${f}"
  else
    rm -f -- "$f"
    echo "removed (${reason}): ${f}"
  fi
  removed=$((removed + 1))
}

# Empty session transcripts (start-created, never written).
while IFS= read -r -d '' f; do
  remove_one "$f" "0-byte"
done < <(find "$LOG_DIR" -maxdepth 1 -type f -name 'session-*.log' -size 0 -print0 2>/dev/null || true)

# Age-based prune (optional).
if [[ -n "$DAYS" ]]; then
  while IFS= read -r -d '' f; do
    remove_one "$f" "mtime>${DAYS}d"
  done < <(find "$LOG_DIR" -maxdepth 1 -type f -name 'session-*.log' -mtime "+${DAYS}" -print0 2>/dev/null || true)
fi

echo "OK [rotate-logs]: ${removed} removed, dry_run=${DRY_RUN}, dir=${LOG_DIR}"
exit 0
