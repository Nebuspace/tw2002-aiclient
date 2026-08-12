# WO-FIX-CURSOR-PATH-LEAK-HOOK-WORKTREE-CWD-BLIND

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** MED  
**Refs:** PROCESS-NOTE 2026-08-12T06:07:55Z · `.cursor/hooks/path-leak-gate.sh` · `scripts/path-leak-scan.sh`

## Goal

Cursor path-leak gate must scan the git repo the Shell command actually commits
in (exclusive worktree via `cd` / `git -C`), not only the Cursor workspace root.

## Accept

1. `cd /path/to/worktree && git commit` scans that worktree's staged index.
2. Dirty-unstaged refuse on the scanned repo gets a distinct deny message from
   a real operator-home path leak.
3. Non-commit shell commands still allow.

## Proof

Manual: staged commit in exclusive worktree passes hook while workspace root
has dirty/untracked files. `bash -n` on hook script.
