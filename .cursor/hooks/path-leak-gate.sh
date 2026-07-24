#!/usr/bin/env bash
# Cursor beforeShellExecution hook — block `git commit` when staged content
# contains operator-home absolute paths (`/Users/<user>/` or `/home/<user>/`).
#
# Wired from `.cursor/hooks.json` with failClosed: true — this script MUST
# always emit exactly one JSON permission object on stdout (even on errors),
# or Cursor will deny the tool call.
#
# Self-filters to real `git commit` invocations (no hooks.json matcher) so
# agent scripts that merely mention the words are not gated.

set +e
set -u

exec 3>&1 1>&2
emit() { printf '%s\n' "$1" >&3; }

allow() { emit '{"permission":"allow"}'; exit 0; }
deny() {
  emit "{\"permission\":\"deny\",\"user_message\":\"$1\",\"agent_message\":\"$2\"}"
  exit 2
}

# Trap unexpected failures → deny (fail closed), never silent empty stdout.
trap 'emit "{\"permission\":\"deny\",\"user_message\":\"path-leak gate crashed\",\"agent_message\":\"Hook exited unexpectedly; treat as deny (failClosed).\"}"; exit 2' ERR

input=$(cat || true)

# Extract .command without jq/python (sparse worker hosts).
cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
cmd=$(printf '%s' "$cmd" | sed 's/\\n/ /g; s/\\"/"/g; s/\\\\/\\/g')

if ! printf '%s' "$cmd" | grep -qE '(^|[[:space:]])git[[:space:]]+commit([[:space:]]|$)'; then
  allow
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  deny "path-leak gate: not in a git repo" "Cannot scan staged diff without a work tree."
fi
SCAN="${ROOT}/scripts/path-leak-scan.sh"

if [[ ! -x "$SCAN" ]]; then
  deny "path-leak gate: scanner missing" "Restore scripts/path-leak-scan.sh and chmod +x it."
fi

if ! "$SCAN"; then
  deny "path-leak gate blocked this commit: staged content has /Users/<user>/ (or /home/<user>/) paths." "Relativize absolute operator-home paths in the staged diff, then retry the commit."
fi

allow
