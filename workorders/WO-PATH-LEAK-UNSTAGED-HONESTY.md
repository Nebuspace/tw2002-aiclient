# WO-PATH-LEAK-UNSTAGED-HONESTY — path-leak-scan must not exit 0 on "nothing staged"

**Status:** OPEN · READY · tooling  
**Posted:** 2026-07-27T20:50:00Z · hub from CC #114 STATUS finding  
**Seat:** Cursor or hub  
**Depends:** none  
**Refs:** CC 2026-07-27T20:20 · `path-leak-scan.sh` · pre-commit still OK post-stage

## Goal

Manual `path-leak-scan.sh` with dirty-but-unstaged work prints "no staged changes" and exits **0** — indistinguishable from a real clean pass. Change to non-zero (or explicit FAIL) when the working tree has unstaged/untracked modifications and the index is empty, **or** scan the working tree when invoked with a documented `--worktree` / default-preflight mode.

## Accept

1. Vacuous "nothing staged" is not exit 0 when the tree is dirty (or the tool refuses with a clear message + non-zero).
2. Staged clean path still exits 0; staged leak still exits non-zero (negative control).
3. Pre-commit post-stage path unchanged / still fires.
4. PR + STATUS.

## Proof

Scripted inject: dirty unstaged with a fake operator-home absolute path → must not look green; staged leak → fail; staged clean → pass.
