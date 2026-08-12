#!/usr/bin/env bash
# Cursor beforeShellExecution hook — block `git commit` when staged content
# contains operator-home absolute paths (`/Users/<user>/` or `/home/<user>/`).
#
# Wired from `.cursor/hooks.json` with failClosed: false — when the Cursor
# worker cannot execute command hooks, shell stays usable (WO-CURSOR-HOOK-
# RECOVERY-HARDENING). Commit-time fail-closed remains `scripts/githooks/
# pre-commit`. When this hook *does* run, it must still emit exactly one
# JSON permission object on stdout (even on errors).
#
# Self-filters to real `git commit` invocations (no hooks.json matcher) so
# agent scripts that merely mention the words are not gated.
#
# WO-FIX-CURSOR-PATH-LEAK-HOOK-WORKTREE-CWD-BLIND: resolve the git root from
# the Shell command's `cd` / `git -C` target, not only the Cursor workspace
# checkout, so exclusive worktree commits scan the right index.

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

strip_quotes() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  if [[ "$s" == \"*\" && "$s" == *\" ]]; then
    s="${s#\"}"
    s="${s%\"}"
  elif [[ "$s" == \'*\' && "$s" == *\' ]]; then
    s="${s#\'}"
    s="${s%\'}"
  fi
  printf '%s' "$s"
}

resolve_scan_root() {
  local command="$1"
  local fallback="$2"
  local dir="$fallback"
  local segment target

  while IFS= read -r segment; do
    segment="${segment#"${segment%%[![:space:]]*}"}"
    segment="${segment%"${segment##*[![:space:]]}"}"
    [[ -z "$segment" ]] && continue
    if [[ "$segment" =~ ^cd[[:space:]]+(.+)$ ]]; then
      target="$(strip_quotes "${BASH_REMATCH[1]}")"
      if [[ -d "$target" ]]; then
        dir="$target"
      fi
    elif [[ "$segment" =~ ^git[[:space:]]+-C[[:space:]]+([^[:space:]]+)([[:space:]]|$) ]]; then
      target="$(strip_quotes "${BASH_REMATCH[1]}")"
      if [[ -d "$target" ]]; then
        dir="$target"
      fi
    fi
  done < <(printf '%s' "$command" | tr ';' '\n' | sed 's/&&/\n/g')

  if git -C "$dir" rev-parse --show-toplevel >/dev/null 2>&1; then
    git -C "$dir" rev-parse --show-toplevel
    return 0
  fi
  printf '%s' "$fallback"
}

FALLBACK_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
ROOT="$(resolve_scan_root "$cmd" "$FALLBACK_ROOT")"
if [[ -z "$ROOT" ]]; then
  deny "path-leak gate: not in a git repo" "Cannot scan staged diff without a work tree."
fi
SCAN="${ROOT}/scripts/path-leak-scan.sh"

if [[ ! -x "$SCAN" ]]; then
  deny "path-leak gate: scanner missing" "Restore scripts/path-leak-scan.sh and chmod +x it."
fi

scan_out=""
scan_rc=0
scan_out="$(cd "$ROOT" && "$SCAN" 2>&1)" || scan_rc=$?

if [[ "$scan_rc" -ne 0 ]]; then
  if printf '%s' "$scan_out" | grep -q 'working tree is dirty'; then
    deny "path-leak gate: scanned repo has no staged changes (working tree dirty)." "The hook scanned ${ROOT}. Stage intended paths in that worktree, or commit from the tree that holds your staged diff."
  fi
  if printf '%s' "$scan_out" | grep -q 'operator-home absolute path'; then
    deny "path-leak gate blocked this commit: staged content has /Users/<user>/ (or /home/<user>/) paths." "Relativize absolute operator-home paths in the staged diff, then retry the commit."
  fi
  deny "path-leak gate: scan failed." "path-leak-scan.sh exited ${scan_rc} for ${ROOT}. See hook stderr for scanner output."
fi

allow
