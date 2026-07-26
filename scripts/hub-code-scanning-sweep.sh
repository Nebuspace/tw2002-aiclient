#!/usr/bin/env bash
# hub-code-scanning-sweep.sh — Pre-merge code-scanning alert sweep (orchestrator-only).
#
# Code scanning alerts typically appear on the default branch *after* merge, with
# GitHub scan lag. This script is run at the START of the hub merge ritual for
# the *current* PR — it does NOT block that merge. New open alerts are treated as
# lagging signals from recently merged work (~PR N-1 / N-2), banked as remediation
# WOs, then the current merge continues (suite → live-prove → merge → cleanup).
#
# Usage:
#   ./scripts/hub-code-scanning-sweep.sh [--repo OWNER/NAME]
#
# State (last-seen alert numbers) lives outside the public repo:
#   ${CODE_SCANNING_SEEN_FILE:-$HOME/github/Nebuspace/.samantha/coord/code-scanning-seen.json}
#
# Exit 0 always for "sweep completed" (even when new alerts found) — finding alerts
# must not fail the merge ritual. Exit non-zero only on API/tool failure.

set -euo pipefail

REPO="${REPO:-Nebuspace/tw2002-aiclient}"
# State lives outside this public repo (orchestrator coord-dir). Override with
# CODE_SCANNING_SEEN_FILE or NEBUSPACE_ROOT; never hardcode a personal home path.
if [[ -n "${CODE_SCANNING_SEEN_FILE:-}" ]]; then
  SEEN_FILE="$CODE_SCANNING_SEEN_FILE"
elif [[ -n "${NEBUSPACE_ROOT:-}" ]]; then
  SEEN_FILE="${NEBUSPACE_ROOT}/.samantha/coord/code-scanning-seen.json"
else
  # Walk up from this script: …/tw2002-aiclient/scripts → sibling Nebuspace/ or parent.
  _here=$(cd "$(dirname "$0")" && pwd)
  _cand=""
  if [[ -d "${_here}/../../.samantha/coord" ]]; then
    _cand="${_here}/../../.samantha/coord/code-scanning-seen.json"
  elif [[ -d "${_here}/../../../Nebuspace/.samantha/coord" ]]; then
    _cand="${_here}/../../../Nebuspace/.samantha/coord/code-scanning-seen.json"
  fi
  SEEN_FILE="${_cand:-${TMPDIR:-/tmp}/tw2002-code-scanning-seen.json}"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--repo OWNER/NAME]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$(dirname "$SEEN_FILE")"
if [[ ! -f "$SEEN_FILE" ]]; then
  echo '{"repo":"'"$REPO"'","alert_numbers":[],"updated_at":null}' >"$SEEN_FILE"
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

if ! gh api "repos/${REPO}/code-scanning/alerts?state=open&per_page=100" >"$TMP" 2>/tmp/hub-codescan-api.err; then
  echo "ERROR: code-scanning API failed for $REPO" >&2
  cat /tmp/hub-codescan-api.err >&2 || true
  exit 1
fi

python3 - "$TMP" "$SEEN_FILE" "$REPO" <<'PY'
import json, sys
from datetime import datetime, timezone

alerts_path, seen_path, repo = sys.argv[1], sys.argv[2], sys.argv[3]
alerts = json.load(open(alerts_path))
seen = json.load(open(seen_path))
prev = set(seen.get("alert_numbers") or [])
now_nums = []
rows = []
for a in alerts:
    n = a.get("number")
    if n is None:
        continue
    now_nums.append(n)
    rule = (a.get("rule") or {}).get("id") or "?"
    sev = (a.get("rule") or {}).get("severity") or "?"
    inst = a.get("most_recent_instance") or {}
    loc = inst.get("location") or {}
    path = loc.get("path") or "?"
    line = loc.get("start_line")
    msg = ((inst.get("message") or {}).get("text") or "")[:120]
    url = a.get("html_url") or ""
    rows.append((n, rule, sev, path, line, msg, url))

now_set = set(now_nums)
new = sorted(now_set - prev)
gone = sorted(prev - now_set)

print(f"code-scanning sweep · {repo}")
print(f"  open={len(now_nums)}  previously_seen={len(prev)}  new={len(new)}  resolved_since={len(gone)}")
if new:
    print("  NEW (lagging — likely recent merges, NOT the PR about to merge):")
    for n, rule, sev, path, line, msg, url in rows:
        if n not in new:
            continue
        loc = f"{path}:{line}" if line else path
        print(f"    #{n} [{sev}] {rule} · {loc}")
        print(f"         {msg}")
        if url:
            print(f"         {url}")
    print("  → bank remediation WO(s); do NOT block current merge.")
else:
    print("  no new open alerts since last sweep.")

if gone:
    print(f"  resolved/disappeared since last sweep: {gone}")

seen["repo"] = repo
seen["alert_numbers"] = sorted(now_set)
seen["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
seen["last_new"] = new
json.dump(seen, open(seen_path, "w"), indent=2)
print(f"  wrote {seen_path}")
PY
