#!/usr/bin/env bash
# Cursor beforeShellExecution hook — block `git commit` when staged content
# contains operator-home absolute paths (`/Users/<user>/` or `/home/<user>/`).
#
# Wired from `.cursor/hooks.json`. Mirrors Claude Code PreToolUse leak intent.
#
# Cursor contract: exactly ONE JSON permission object on stdout.
# Human-readable diagnostics go to stderr.

set -uo pipefail

exec 3>&1 1>&2
emit() { printf '%s\n' "$1" >&3; }

allow() { emit '{"permission":"allow"}'; exit 0; }
deny() {
  local user="$1" agent="$2"
  # Minimal JSON escaping for short fixed messages
  emit "{\"permission\":\"deny\",\"user_message\":\"${user}\",\"agent_message\":\"${agent}\"}"
  exit 2
}

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  allow
fi
SCAN="${ROOT}/scripts/path-leak-scan.sh"

input=$(cat || true)

# Extract .command without requiring jq/python (worker hosts can be sparse).
cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
# Unescape common JSON \" and \\ sequences lightly
cmd=$(printf '%s' "$cmd" | sed 's/\\n/ /g; s/\\"/"/g; s/\\\\/\\/g')

# Only gate real git commit invocations (not scripts that merely mention the words).
case " $cmd " in
  *" git commit "*|*" git commit"$'\n'*|git\ commit\ *) ;;
  *)
    # Also match command that starts with git commit
    if ! printf '%s' "$cmd" | grep -qE '(^|[[:space:]])git[[:space:]]+commit([[:space:]]|$)'; then
      allow
    fi
    ;;
esac

if [[ ! -x "$SCAN" ]]; then
  echo "WARN [path-leak-gate]: scanner missing or not executable: $SCAN" >&2
  deny "path-leak gate: scanner missing" "Restore scripts/path-leak-scan.sh and chmod +x it."
fi

if ! "$SCAN"; then
  deny "path-leak gate blocked this commit: staged content has /Users/<user>/ (or /home/<user>/) paths." "Relativize absolute operator-home paths in the staged diff, then retry the commit."
fi

allow
